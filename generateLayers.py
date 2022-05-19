# Name: generateLayers.py
# Description: Generates XAPO data and stores it in the SQL Server.
# Requirements: Python 2.7

# Import system modules
import textwrap
import arcpy
import os, time
import COSBDebug

COSBDebug.successEmailList = []
COSBDebug.failureEmailList = ['DL-ITApplicationsDivision@southbendin.gov']
COSBDebug.emailLogOnSuccess = False

def addressLayer(SBAddrPts, countyAddrPts, parcels, cityLimits, outputAddress, outSDE):
    inMem = "in_memory"
    memAddrs = inMem + "/memAddrs"
    memCountyAddrs = inMem + "/memCountyAddrs"
    memMerge = inMem + "/memMerge"
    memTemp = inMem + "/memTemp"

    # Creating feature layers
    missing_lyr = "missing_lyr"
    addrSB_lyr = "addrSB_lyr"
    parcelNoSBAddr_lyr = "parcelNoSBAddr_lyr"

    addressFields = ["PARCELSTAT", "Street_Number", "Street_Apt_Num", "Street_Dir", "Street_Name", "Street_Suffix",
                     "Post_Street_Dir", "City", "State", "Zip", "X_WGS84", "Y_WGS84", "enQuesta_PremiseID", "SHAPE",
                     "OBJECTID"]

    # Making zip field into length 10 to match the City's format - if not, merge throws an error
    # Using inMem feature class and editing it instead of field mapping because field mapping is a lot more code
    arcpy.FeatureClassToFeatureClass_conversion(countyAddrPts, inMem, "memCountyAddrs")
    arcpy.AddField_management(memCountyAddrs, "PROPERTYZI", "TEXT", "", "", "10", "", "NULLABLE", "NON_REQUIRED", "")
    arcpy.CalculateField_management(memCountyAddrs, "PROPERTYZI", "!Zip!", "PYTHON_9.3")
    arcpy.DeleteField_management(memCountyAddrs, "Zip")
    # Copying inMem feature class to feature layer because the rest of the code uses missing_lyr and I don't want to change it
    arcpy.MakeFeatureLayer_management(memCountyAddrs, missing_lyr)
    arcpy.MakeFeatureLayer_management(SBAddrPts, addrSB_lyr)

    COSBDebug.log("Selecting SB master address points that match the scrubbed parcels")
    # Select address points of the scrubbed SB parcels
    arcpy.SelectLayerByLocation_management(addrSB_lyr, "INTERSECT", parcels)

    COSBDebug.log("{} corresponding scrubbed SB master address points within SB city limits.".format(
        arcpy.GetCount_management(addrSB_lyr)))

    COSBDebug.log("Selecting scrubbed parcels that do NOT have a SB Master address point")
    arcpy.MakeFeatureLayer_management(parcels, parcelNoSBAddr_lyr)
    arcpy.SelectLayerByLocation_management(parcelNoSBAddr_lyr, "INTERSECT", addrSB_lyr)
    arcpy.SelectLayerByAttribute_management(parcelNoSBAddr_lyr, "SWITCH_SELECTION")

    # Select the scrubbed parcels that don't have SB master address points
    arcpy.SelectLayerByLocation_management(missing_lyr, "COMPLETELY_WITHIN", parcelNoSBAddr_lyr)
    COSBDebug.log("{} scrubbed parcels didn't have a SB master address point.".format(
        arcpy.GetCount_management(parcelNoSBAddr_lyr)))
    COSBDebug.log("{} selected County master address points that match the scrubbed SB parcels where there isn't a SB master address point.".format(
            arcpy.GetCount_management(missing_lyr)))

    COSBDebug.log("Merging missing County master address points and SB master address points for a full address point layer")
    # Merging SB address points in SB with PARCELSTAT field with \"missing\" County addresses
    arcpy.Merge_management([missing_lyr, addrSB_lyr], memMerge)
    COSBDebug.log("{} total merged address points.".format(arcpy.GetCount_management(memMerge)))

    COSBDebug.log("Spatial joining parcel numbers from scrubbed parcels to address points")
    arcpy.SpatialJoin_analysis(memMerge, parcels, memTemp, "JOIN_ONE_TO_MANY")

    COSBDebug.log("Including address points that are actually within the city")
    arcpy.SpatialJoin_analysis(memTemp, cityLimits, memAddrs, "JOIN_ONE_TO_MANY", "#", "#", "WITHIN")

    arcpy.FeatureClassToFeatureClass_conversion(SBAddrPts, inMem, "memAddrs")
    dropExtraFields(memAddrs, addressFields)

    # Add field and calculate: SERV_PROV_CODE
    arcpy.AddField_management(memAddrs, "SERV_PROV_CODE", "TEXT", "", "", "15", "", "NULLABLE", "NON_REQUIRED", "")
    arcpy.CalculateField_management(memAddrs, "SERV_PROV_CODE", "'SOUTHBENDIN'", "PYTHON_9.3", "")

    # Add field and calculate: SOURCE_SEQ_NBR
    arcpy.AddField_management(memAddrs, "SOURCE_SEQ_NBR", "SHORT", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")
    arcpy.CalculateField_management(memAddrs, "SOURCE_SEQ_NBR", "259", "PYTHON_9.3", "")

    # Add field and calculate: L1_UNIT_START
    arcpy.AddField_management(memAddrs, "UNIT_TYPE", "TEXT", "", "", "6", "", "NULLABLE", "NON_REQUIRED", "")
    codeBlock_ut = textwrap.dedent("""\
    def UnitType(UnitStart):    
        if (UnitStart is not None):        
            return \"Unit\"    
        else:        
            return None""")
    arcpy.CalculateField_management(memAddrs, "UNIT_TYPE", "UnitType(!Street_Apt_Num!)",
                                    "PYTHON_9.3", codeBlock_ut)

    # Add field and calculate: COUNTY
    arcpy.AddField_management(memAddrs, "COUNTY", "TEXT", "", "", "30", "", "NULLABLE", "NON_REQUIRED", "")
    arcpy.CalculateField_management(memAddrs, "COUNTY", "\"ST. JOSEPH\"", "PYTHON_9.3")

    # Add field and calculate: L1_SITUS_COUNTRY
    arcpy.AddField_management(memAddrs, "COUNTRY", "TEXT", "", "", "30", "", "NULLABLE", "NON_REQUIRED", "")
    arcpy.CalculateField_management(memAddrs, "COUNTRY", "\"UNITED STATES\"", "PYTHON_9.3")

    # Add field and calculate: ATTRIB_TEMP_NAME_1
    arcpy.AddField_management(memAddrs, "ATTRIB_TEMP_NAME_1", "TEXT", "", "", "30", "", "NULLABLE", "NON_REQUIRED", "")
    arcpy.CalculateField_management(memAddrs, "ATTRIB_TEMP_NAME_1", "\"AddressAttributes\"", "PYTHON_9.3")

    # Add field and calculate: ATTRIB_NAME_1
    arcpy.AddField_management(memAddrs, "ATTRIB_NAME_1", "TEXT", "", "", "30", "", "NULLABLE", "NON_REQUIRED", "")
    arcpy.CalculateField_management(memAddrs, "ATTRIB_NAME_1", "\"LocationID\"", "PYTHON_9.3")

    # Add field and calculate: ADDRESS1
    arcpy.AddField_management(memAddrs, "ADDRESS1", "TEXT", "", "", "200", "", "NULLABLE", "NON_REQUIRED", "")
    codeBlock_a1 = textwrap.dedent("""\
    def Line1(houseStart, strDir, strName, strSuf, strSufDir):
        if strDir is not None:
            if strSuf is not None:
                return "{} {} {} {} {}".format(houseStart, strDir, strName, strSuf, strSufDir if strSufDir else '').strip()
            else:
                return "{} {} {} {}".format(houseStart, strDir, strName, strSufDir if strSufDir else '').strip()
        else:
            if strSuf is not None:
                return "{} {} {} {}".format(houseStart, strName, strSuf, strSufDir if strSufDir else '').strip()
            else:
                return "{} {} {}".format(houseStart, strName, strSufDir if strSufDir else '').strip()
    """)
    arcpy.CalculateField_management(memAddrs, "ADDRESS1",
                                    "Line1(!Street_Number!, !Street_Dir!, !Street_Name!, !Street_Suffix!, !Post_Street_Dir!)",
                                    "PYTHON_9.3", codeBlock_a1)

    # Add field and calculate: ADDRESS2
    arcpy.AddField_management(memAddrs, "ADDRESS2", "TEXT", "", "", "200", "", "NULLABLE", "NON_REQUIRED", "")
    codeBlock_a2 = textwrap.dedent("""\
    def Line2(number):
        if number is not None:
            return \"Unit\" + " " + number
        else:
            return None""")
    arcpy.CalculateField_management(memAddrs, "ADDRESS2", "Line2(!Street_Apt_Num!)", "PYTHON_9.3",
                                    codeBlock_a2)

    # Add field and calculate: FULL_ADDRESS
    arcpy.AddField_management(memAddrs, "FULL_ADDRESS", "TEXT", "", "", "1024", "", "NULLABLE", "NON_REQUIRED", "")
    # strip() takes care of empty zip
    codeBlock_fa = textwrap.dedent("""\
    def FullAddress(Line1, Line2, City, State, Zip):
        if (Line2 is not None):
            return "{} {} {} {} {}".format(Line1, Line2, City, State, Zip if Zip else '').strip()
        else:
            return "{} {} {} {}".format(Line1, City, State, Zip if Zip else '').strip()
    """)
    arcpy.CalculateField_management(memAddrs, "FULL_ADDRESS",
                                    "FullAddress(!ADDRESS1!, !ADDRESS2!, !City!, !State!, !Zip!)", "PYTHON_9.3",
                                    codeBlock_fa)

    try:
        arcpy.CopyFeatures_management(memAddrs, outputAddress)
        arcpy.CopyFeatures_management(memAddrs, outputAddress[0:-11])

    except arcpy.ExecuteError:
        # Copying features didn't work on first try. Trying to get exclusive schema lock to retry.
        # Disabling connectivity to database
        arcpy.AcceptConnections(outSDE, False)
        # Disconnecting all users
        arcpy.DisconnectUser(outSDE, 'ALL')
        arcpy.CopyFeatures_management(memAddrs, outputAddress)
        arcpy.CopyFeatures_management(memAddrs, outputAddress[0:-11])
        arcpy.AcceptConnections(outSDE, True)

def ownerLayer(parcels, outputOwner, outSDE):
    inMem = "in_memory"
    memOwner = inMem + "/memOwner"
    memOwnerPts = inMem + "/memOwnerPts"

    ownerFields = ["PARCELSTAT", "NAME_1", "MAILINGADD", "MAILINGA_1", "MAILINGCIT", "MAILINGSTA", "MAILINGZIP",
                   "PARCELID", "SHAPE", "OBJECTID"]
    arcpy.FeatureClassToFeatureClass_conversion(parcels, inMem, "memOwner")
    dropExtraFields(memOwner, ownerFields)

    # Add and calculate field: SOURCE_SEQ_NBR
    arcpy.AddField_management(memOwner, "SOURCE_SEQ_NBR", "SHORT", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")
    arcpy.CalculateField_management(memOwner, "SOURCE_SEQ_NBR", "\"259\"", "PYTHON_9.3")

    # Add and calculate field: Add Field: ISPRIMARY
    arcpy.AddField_management(memOwner, "ISPRIMARY", "TEXT", "", "", "1", "", "NULLABLE", "NON_REQUIRED", "")
    arcpy.CalculateField_management(memOwner, "ISPRIMARY", "\"Y\"", "PYTHON_9.3")

    # Add and calculate field: MAILINGCOUNTRY
    arcpy.AddField_management(memOwner, "MAILINGCOUNTRY", "TEXT", "", "", "30", "", "NULLABLE", "NON_REQUIRED", "")
    arcpy.CalculateField_management(memOwner, "MAILINGCOUNTRY", "\"UNITED STATES OF AMERICA\"", "PYTHON_9.3")

    arcpy.FeatureToPoint_management(memOwner, memOwnerPts, "INSIDE")

    try:
        arcpy.CopyFeatures_management(memOwner, outputOwner)
        arcpy.CopyFeatures_management(memOwner, outputOwner[0:-11])

    except arcpy.ExecuteError:
        # Copying features didn't work on first try. Trying to get exclusive schema lock to retry.
        # Disabling connectivity to database
        arcpy.AcceptConnections(outSDE, False)
        # Disconnecting all users
        arcpy.DisconnectUser(outSDE, 'ALL')
        arcpy.CopyFeatures_management(memOwner, outputOwner)
        arcpy.CopyFeatures_management(memOwner, outputOwner[0:-11])
        arcpy.AcceptConnections(outSDE, True)

def parcelLayer(memPDI, outputParcel, outSDE):
    parcelFields = ["PARCELSTAT", "Num", "REALIMPROV", "REALLANDVA", "LEGALDESCR", "MAPREFEREN", "ACREAGE",
                    "InspectorAreas", "SHAPE", "OBJECTID", "SHAPE.STLength()", "SHAPE.STArea()","InspectorAreas_1"]

    dropExtraFields(memPDI, parcelFields)

    # Add and calculate field: SOURCE_SEQ_NBR
    arcpy.AddField_management(memPDI, "SOURCE_SEQ_NBR", "SHORT", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")
    arcpy.CalculateField_management(memPDI, "SOURCE_SEQ_NBR", "\"259\"", "PYTHON_9.3")
    
    arcpy.management.AlterField(memPDI, "InspectorAreas_1", "HousingAreas", "HousingAreas", "SHORT", 2, "NULLABLE", "DO_NOT_CLEAR")
    arcpy.management.AlterField(memPDI, "InspectorAreas", "EnvironmentalAreas", "EnvironmentalAreas", "SHORT", 2, "NULLABLE", "DO_NOT_CLEAR")

    try:
        arcpy.CopyFeatures_management(memPDI, outputParcel)
        arcpy.CopyFeatures_management(memPDI, outputParcel[0:-11])

    except arcpy.ExecuteError:
        # Copying features didn't work on first try. Trying to get exclusive schema lock to retry.
        # Disabling connectivity to database
        arcpy.AcceptConnections(outSDE, False)
        # Disconnecting all users
        arcpy.DisconnectUser(outSDE, 'ALL')
        arcpy.CopyFeatures_management(memPDI, outputParcel)
        arcpy.CopyFeatures_management(memPDI, outputParcel[0:-11])
        arcpy.AcceptConnections(outSDE, True)


# Remove all output fields you don't want.
def dropExtraFields(loc, passFields):
    passTypes = ["OID", "Geometry", "Guid"]
    dropFields = []
    for field in arcpy.ListFields(loc):
        if field.name not in passFields and field.type not in passTypes:
            dropFields.append(field.name)
    arcpy.DeleteField_management(loc, dropFields)

@COSBDebug.COSBEmails
def main():
    # Set local variables
    scriptTime = time.strftime("%Y-%m-%d_%H %M %S")
    print "Script started running at", scriptTime

    todaysDate = time.strftime("%Y_%m_%d")

    # SDE file locations
    SDEFolder = r"\\cosb-fs1\GISSYS\SBCommons\Connections\Prod"
    outSDE = r"\\cosb-fs1\GISSYS\GISSYS Connection Files\XAPO_OS@cosb-sql.sde"

    # Output Locations
    outputAddress = os.path.join(outSDE, "XAPO.DBO.Address_" + todaysDate)
    outputOwner = os.path.join(outSDE, "XAPO.DBO.Owner_" + todaysDate)
    outputParcel = os.path.join(outSDE, "XAPO.DBO.Parcel_" + todaysDate)

    landRecordsSDE = os.path.join(r"\\cosb-fs1\GISSYS\Admin\GISConfigStore\10.3.1\DatabaseConnections",
                                  "LandRecords_OS@cosb-sql1.sde")
    propertiesSDE = os.path.join(SDEFolder, "SBCommons_Properties@cosb-sql_gis.sde")
    zonesBoundariesSDE = os.path.join(SDEFolder, "SBCommons_ZonesBoundaries@cosb-sql_gis.sde")

    # TEST LOCATIONS
    # landRecordsSDE = os.path.join(r"\\cosb-fs1\GISSYS\Admin\GISConfigStore\10.3.1\DatabaseConnections",
    #                               "LandRecords_OS@cosb-sql1.sde")
    # propertiesSDE = os.path.join(SDEFolder, "SBCommons_Properties@cosb-sql-test2-gis.sde")
    # zonesBoundariesSDE = os.path.join(SDEFolder, "SBCommons_ZonesBoundaries@cosb-sql-test2-gis.sde")

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
    parcels = os.path.join(propertiesSDE, "SBCommons.PROPERTIES.Parcels")
    councilDistricts = os.path.join(zonesBoundariesSDE, "SBCommons.ZONESBOUNDARIES.CityCouncilDistricts")
    inspectorAreas = os.path.join(landRecordsSDE, "LandRecords.DBO.CodeInspectorAreas")
    SBAddrPts = os.path.join(propertiesSDE, "SBCommons.Properties.ADDRESSPOINTS")
    countyAddrPts = os.path.join(propertiesSDE, "SBCommons.Properties.AddressPoints_County")
    cityLimits = os.path.join(zonesBoundariesSDE, "SBCommons.ZonesBoundaries.CityLimits")
    
    #Make feature layer for inspection areas
    arcpy.MakeFeatureLayer_management(inspectorAreas, IA)

    # Joins Parcel and City Council Districts
    arcpy.SpatialJoin_analysis(parcels, councilDistricts, memPD, "JOIN_ONE_TO_ONE", "KEEP_ALL", "", "HAVE_THEIR_CENTER_IN", "", "")

    # Generates owner layer
    ownerLayer(parcels, outputOwner, outSDE)
    
    arcpy.SelectLayerByAttribute_management(IA, "NEW_SELECTION", "Area_Type = 'Environmental'")

    # Joins Parcel and City Council Districts and Inspector Areas
    arcpy.SpatialJoin_analysis(memPD, IA, memPDI, "JOIN_ONE_TO_ONE", "KEEP_ALL", "", "HAVE_THEIR_CENTER_IN", "", "")
    
    arcpy.SelectLayerByAttribute_management(IA, "NEW_SELECTION", "Area_Type = 'Housing'")

    # Joins Parcel and City Council Districts and Inspector Areas
    arcpy.SpatialJoin_analysis(memPDI, IA, memPDII, "JOIN_ONE_TO_ONE", "KEEP_ALL", "", "HAVE_THEIR_CENTER_IN", "", "")

    # Generates parcel layer
    parcelLayer(memPDII, outputParcel, outSDE)
    # Generates address layer
    addressLayer(SBAddrPts, countyAddrPts, parcels, cityLimits, outputAddress, outSDE)
main()