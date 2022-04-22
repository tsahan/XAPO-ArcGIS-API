# Description: Generates XAPO data and stores it in the SQL Server.
# Requirements: Python 2.7

# Import system modules
import arcpy
import os, time
import COSBDebug
import ownerLayer, parcelLayer, addressLayer

COSBDebug.successEmailList = []
COSBDebug.failureEmailList = []
COSBDebug.emailLogOnSuccess = False
    
@COSBDebug.COSBEmails
def main():
    # Set local variables
    scriptTime = time.strftime("%Y-%m-%d_%H %M %S")
    print "Script started running at", scriptTime

    # SDE test locations
    SDEFolder = ""
    outSDE = ""

    # Output Locations
    outputAddress = os.path.join(outSDE, "XAPO.DBO.Address")
    outputOwner = os.path.join(outSDE, "XAPO.DBO.Owner")
    outputParcel = os.path.join(outSDE, "XAPO.DBO.Parcel")
    outputAP = os.path.join(outSDE, "XAPO.DBO.AP")

    # TEST LOCATIONS
    landRecordsSDE = ""
    propertiesSDE = ""
    zonesBoundariesSDE = ""

    arcpy.env.overwriteOutput = True

    # Memory Locations
    inMem = "in_memory"
    # Parcels + CityCouncilDistricts
    memPD = os.path.join(inMem, "memPD")
    # Parcels + CityCouncilDistricts + CodeInspectorAreas(Environmental)
    memPDI = os.path.join(inMem, "memPDI")
    # Parcels + CityCouncilDistricts + CodeInspectorAreas(Environmental) + CodeInspectorAreas(Housing)
    memPDII = os.path.join(inMem, "memPDII")
    # Inspection Areas
    IA = "inspareas"

    # Data read
    parcels = ""
    councilDistricts = ""
    inspectorAreas = ""
    SBAddrPts = ""
    countyAddrPts = ""
    cityLimits = ""
    
    #Make feature layer for inspection areas
    arcpy.MakeFeatureLayer_management(inspectorAreas, IA)

    # Joins Parcel and City Council Districts
    arcpy.SpatialJoin_analysis(parcels, councilDistricts, memPD, "JOIN_ONE_TO_ONE", "KEEP_ALL", "", "HAVE_THEIR_CENTER_IN", "", "")

    # Generates owner layer
    ownerLayer.ownerLayer(parcels, outputOwner, outSDE)
    
    arcpy.SelectLayerByAttribute_management(IA, "NEW_SELECTION", "Area_Type = 'Environmental'")

    # Joins Parcel and City Council Districts and Inspector Areas
    arcpy.SpatialJoin_analysis(memPD, IA, memPDI, "JOIN_ONE_TO_ONE", "KEEP_ALL", "", "HAVE_THEIR_CENTER_IN", "", "")
    
    arcpy.SelectLayerByAttribute_management(IA, "NEW_SELECTION", "Area_Type = 'Housing'")

    # Joins Parcel and City Council Districts and Inspector Areas
    arcpy.SpatialJoin_analysis(memPDI, IA, memPDII, "JOIN_ONE_TO_ONE", "KEEP_ALL", "", "HAVE_THEIR_CENTER_IN", "", "")

    # Generates parcel layer
    parcelLayer.parcelLayer(memPDII, outputParcel, outSDE)
    # Generates address layer
    addressLayer.addressLayer(SBAddrPts, countyAddrPts, parcels, cityLimits, outputAddress, outSDE)

main()