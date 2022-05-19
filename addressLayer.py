import arcpy
import textwrap
import COSBDebug
from misc import dropExtraFields, renameFields

def addressPointstoCentroid(parcels, addPts):
    # To allow overwriting outputs change overwriteOutput option to True.
    # arcpy.env.overwriteOutput = True
    memAddPts = "in_memory/memAddPts"
    
    # Process: Add Join (Add Join) (management)
    COSBDebug.log("Joining parcels and address points")
    arcpy.MakeFeatureLayer_management(parcels, "parcels_lyr")
    Joined = arcpy.management.AddJoin(in_layer_or_view="parcels_lyr", in_field="PARCELSTAT", join_table=addPts, join_field="parcelIdentifier", join_type="KEEP_COMMON")

    # The environment settings set by the EnvManager class are temporary and are only set for the duration of the with block. 
    # AddressCentroidTest = "I:\\Projects\\XAPO\\xapo\\xapo.gdb\\AddressCentroidTest"
    # with arcpy.EnvManager(outputCoordinateSystem="PROJCS['NAD_1983_StatePlane_Indiana_East_FIPS_1301_Feet',GEOGCS['GCS_North_American_1983',DATUM['D_North_American_1983',SPHEROID['GRS_1980',6378137.0,298.257222101]],PRIMEM['Greenwich',0.0],UNIT['Degree',0.0174532925199433]],PROJECTION['Transverse_Mercator'],PARAMETER['False_Easting',328083.3333333333],PARAMETER['False_Northing',820208.3333333333],PARAMETER['Central_Meridian',-85.66666666666667],PARAMETER['Scale_Factor',0.9999666666666667],PARAMETER['Latitude_Of_Origin',37.5],UNIT['Foot_US',0.3048006096012192]]"):
    
    COSBDebug.log("Converting features to points")
    arcpy.management.FeatureToPoint(in_features=Joined, out_feature_class=memAddPts, point_location="INSIDE")

    # Process: Remove Join (Remove Join) (management)
    # Layer_With_Join_Removed = arcpy.management.RemoveJoin(in_layer_or_view=Joined)
    
    COSBDebug.log("Drop extra fields and rename fields without table name")
    for field in arcpy.ListFields(memAddPts):
        if field.name.startswith("SBCommons_"):
            arcpy.DeleteField_management(memAddPts, field.name)
        if field.name.startswith("memAddrs_"):
            arcpy.management.AlterField(memAddPts, field.name, field.name[9:])
     
    # arcpy.CopyFeatures_management(memAddPts, outputAP)
    return memAddPts
    

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

    addressFields = {
        "X_WGS84" : "XCoordinator",
        "Y_WGS84" : "YCoordinator",
        "Street_Number" : "houseNumberStart",
        "Street_Dir" : "streetDirection",
        "Street_Name" : "streetName",
        "Street_Suffix" : "streetSuffix",
        "Post_Street_Dir" : "streetSuffixdirection",
        "Street_Apt_Num" : "unitStart",
        "PARCELSTAT" : "parcelIdentifier",
        "City" : "City",
        "State" : "State",
        "Zip" : "Zip",
        "enQuesta_PremiseID" : "enQuesta_PremiseID"
    }

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

    # Add field and calculate: L1_UNIT_START
    arcpy.AddField_management(memAddrs, "unitType", "TEXT", "", "", "6", "", "NULLABLE", "NON_REQUIRED", "")
    codeBlock_ut = textwrap.dedent("""\
    def UnitType(UnitStart):    
        if (UnitStart is not None):        
            return \"Unit\"    
        else:        
            return None""")
    arcpy.CalculateField_management(memAddrs, "unitType", "UnitType(!Street_Apt_Num!)",
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
    arcpy.AddField_management(memAddrs, "addressLine1", "TEXT", "", "", "200", "", "NULLABLE", "NON_REQUIRED", "")
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
    arcpy.CalculateField_management(memAddrs, "addressLine1",
                                    "Line1(!Street_Number!, !Street_Dir!, !Street_Name!, !Street_Suffix!, !Post_Street_Dir!)",
                                    "PYTHON_9.3", codeBlock_a1)

    # Add field and calculate: ADDRESS2
    arcpy.AddField_management(memAddrs, "addressLine2", "TEXT", "", "", "200", "", "NULLABLE", "NON_REQUIRED", "")
    codeBlock_a2 = textwrap.dedent("""\
    def Line2(number):
        if number is not None:
            return \"Unit\" + " " + number
        else:
            return None""")
    arcpy.CalculateField_management(memAddrs, "addressLine2", "Line2(!Street_Apt_Num!)", "PYTHON_9.3",
                                    codeBlock_a2)

    # Add field and calculate: FULL_ADDRESS
    arcpy.AddField_management(memAddrs, "fullAddress", "TEXT", "", "", "1024", "", "NULLABLE", "NON_REQUIRED", "")
    # strip() takes care of empty zip
    codeBlock_fa = textwrap.dedent("""\
    def FullAddress(Line1, Line2, City, State, Zip):
        if (Line2 is not None):
            return "{} {} {} {} {}".format(Line1, Line2, City, State, Zip if Zip else '').strip()
        else:
            return "{} {} {} {}".format(Line1, City, State, Zip if Zip else '').strip()
    """)
    arcpy.CalculateField_management(memAddrs, "fullAddress",
                                    "FullAddress(!addressLine1!, !addressLine2!, !City!, !State!, !Zip!)", "PYTHON_9.3",
                                    codeBlock_fa)

    # Renaming field names to what they map to in Accela.
    renameFields(memAddrs, addressFields)
    AddPtsCenter = addressPointstoCentroid(parcels, memAddrs)

    try:
        arcpy.CopyFeatures_management(AddPtsCenter, outputAddress)

    except arcpy.ExecuteError:
        # Copying features didn't work on first try. Trying to get exclusive schema lock to retry.
        # Disabling connectivity to database
        arcpy.AcceptConnections(outSDE, False)
        # Disconnecting all users
        arcpy.DisconnectUser(outSDE, 'ALL')
        arcpy.CopyFeatures_management(AddPtsCenter, outputAddress)
        arcpy.AcceptConnections(outSDE, True)
    finally:
        arcpy.AcceptConnections(outSDE, True)       
