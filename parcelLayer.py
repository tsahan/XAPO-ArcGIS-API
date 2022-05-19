import arcpy
import os
import textwrap
from misc import renameFields

def parcelLayer(parcels, councilDistricts, inspectorAreas, contEnforcemnt, outputParcel, outSDE):       
    # Memory Locations
    inMem = "in_memory"
    # Parcels + CityCouncilDistricts
    memPD = os.path.join(inMem, "memPD")
    # Parcels + CityCouncilDistricts + CodeInspectorAreas(Environmental)
    memPDI = os.path.join(inMem, "memPDI")
    # Parcels + CityCouncilDistricts + CodeInspectorAreas(Environmental) + CodeInspectorAreas(Housing)
    memPDII = os.path.join(inMem, "memPDII")
    # Parcels after combining all shapes that have the same PARCELSTAT into one row
    memParcels = os.path.join(inMem, "memParcels")
    # Inspection Areas
    IA = "inspareas"
    combinedParcels = "combinedParcels"
    
    # Parcel fields to rename
    parcelFields = {
        "REALIMPROV" : "improvedValue",
        "Num" : "InspectionDistrict",
        "REALLANDVA" : "landValue",
        "LEGALDESCR" : "legalDesc",
        "MAPREFEREN" : "mapRef",
        "PARCELSTAT" : "parcelNumber",
        "ACREAGE" : "parcelArea",
        "InspectorAreas" : "EnvironmentalAreas",
        "InspectorAreas_1" : "HousingAreas",
        "STATE_PARCEL_ID": "State_Parcel_ID",
        "HEARINGLETTERDATE": "HearingLetterDate",
        "EXPIRATIONDATE": "ExpirationDate"
    }

    #Make feature layer for inspection areas
    arcpy.MakeFeatureLayer_management(inspectorAreas, IA)

    # Joins Parcel and City Council Districts
    arcpy.SpatialJoin_analysis(parcels, councilDistricts, memPD, "JOIN_ONE_TO_ONE", "KEEP_ALL", "", "HAVE_THEIR_CENTER_IN", "", "")

    arcpy.SelectLayerByAttribute_management(IA, "NEW_SELECTION", "Area_Type = 'Environmental'")

    # Joins Parcel and City Council Districts and Inspector Areas
    arcpy.SpatialJoin_analysis(memPD, IA, memPDI, "JOIN_ONE_TO_ONE", "KEEP_ALL", "", "HAVE_THEIR_CENTER_IN", "", "")
    
    arcpy.SelectLayerByAttribute_management(IA, "NEW_SELECTION", "Area_Type = 'Housing'")

    # Joins Parcel and City Council Districts and Inspector Areas
    arcpy.SpatialJoin_analysis(memPDI, IA, memPDII, "JOIN_ONE_TO_ONE", "KEEP_ALL", "", "HAVE_THEIR_CENTER_IN", "", "")

    # Make feature layer for combined data that excludes empty PARCELSTATS
    arcpy.MakeFeatureLayer_management(memPDII, combinedParcels, "PARCELSTAT IS NOT NULL AND PARCELSTAT <> ''")

    # Aggregate parcels
    arcpy.management.Dissolve(combinedParcels, memParcels, dissolve_field="PARCELSTAT", statistics_fields=[["REALIMPROV", "FIRST"], ["REALLANDVA", "FIRST"], ["LEGALDESCR", "FIRST"], ["MAPREFEREN", "FIRST"], ["ACREAGE", "FIRST"], ["Num", "FIRST"], ["InspectorAreas", "FIRST"], ["InspectorAreas_1", "FIRST"]])

    arcpy.AddField_management(memParcels, "UID_FROM_PARCELSTAT", "TEXT", "", "", "50")
    arcpy.CalculateField_management(memParcels, "UID_FROM_PARCELSTAT", "!PARCELSTAT!.replace('-','').replace('.','')",
                                    "PYTHON_9.3")
    
    for field in arcpy.ListFields(memParcels):
        if field.name.startswith("FIRST_"):
            arcpy.management.AlterField(memParcels, field.name, field.name[6:])

    sql = "SELECT * FROM CentralServices.Code.Accela_Continuous_Enforcement"

    # sql = "SELECT * FROM CentralServices.Code.Accela_Continuous_Enforcement"
    # arcpy.management.MakeQueryLayer(contEnforcemnt, "CE", sql)

    arcpy.management.MakeQueryTable(contEnforcemnt, "CE", "ADD_VIRTUAL_KEY_FIELD", "")
    # arcpy.management.MakeQueryTable(contEnforcemnt, "CE", "ADD_VIRTUAL_KEY_FIELD", "", [["LinkTitle", 'State_Parcel_ID'], ["EXPIRATION_x0020_DATE", 'ExpirationDate'],
    #                              ["HEARING_x0020__x0020_OR_x0020_LE", 'HearingLetterDate']], "Status = 'Active'")

    arcpy.management.JoinField(in_data=memParcels, in_field="PARCELSTAT", join_table="CE", join_field="State_Parcel_ID", fields=["State_Parcel_ID", "ExpirationDate", "HearingLetterDate"])
    # We don't need to drop extra fields anymore since Dissolve drops the fields other than specified in statistics_fields. Renaming field names that starts with "FIRST_" after dissolve operation.    
    
    # Add field and calculate: ContinuousEnforcement
    arcpy.AddField_management(memParcels, "ContinuousEnforcement", "TEXT", "", "", "200", "", "NULLABLE", "NON_REQUIRED", "")
    codeblock_ce = textwrap.dedent("""
    def CE(parcelID):
        if parcelID is not None:
            return \"Yes\"
        else:
            return \"No\"""")
    arcpy.CalculateField_management(memParcels, "ContinuousEnforcement", "CE(!State_Parcel_ID!)", "PYTHON_9.3",
                                    codeblock_ce)
                                 
    # Renaming field names to what they map to in Accela.       
    renameFields(memParcels, parcelFields)

    try:
        arcpy.CopyFeatures_management(memParcels, outputParcel)

    except arcpy.ExecuteError:
        # Copying features didn't work on first try. Trying to get exclusive schema lock to retry.
        # Disabling connectivity to database
        arcpy.AcceptConnections(outSDE, False)
        # Disconnecting all users
        arcpy.DisconnectUser(outSDE, 'ALL')
        arcpy.CopyFeatures_management(memParcels, outputParcel)
        arcpy.AcceptConnections(outSDE, True)
    finally:
        arcpy.AcceptConnections(outSDE, True)