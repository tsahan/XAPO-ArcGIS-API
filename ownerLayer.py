import arcpy
from misc import dropExtraFields, renameFields

def ownerLayer(parcels, outputOwner, outSDE):
    inMem = "in_memory"
    memOwner = inMem + "/memOwner"
    memOwnerPts = inMem + "/memOwnerPts"

    ownerFields = {
        "MAILINGADD" : "mailAddress1",
        "MAILINGA_1" : "mailAddress2",
        "MAILINGCIT" : "mailCity",
        "MAILINGSTA" : "mailState",
        "MAILINGZIP" : "mailZip",
        "NAME_1" : "ownerFullName",
        "PARCELSTAT" : "parcelIdentifier",     
    }

    arcpy.FeatureClassToFeatureClass_conversion(parcels, inMem, "memOwner")
    dropExtraFields(memOwner, ownerFields)

    # Add and calculate field: Add Field: ISPRIMARY
    arcpy.AddField_management(memOwner, "ISPRIMARY", "TEXT", "", "", "1", "", "NULLABLE", "NON_REQUIRED", "")
    arcpy.CalculateField_management(memOwner, "ISPRIMARY", "\"Y\"", "PYTHON_9.3")

    # Add and calculate field: MAILINGCOUNTRY
    arcpy.AddField_management(memOwner, "mailCountry", "TEXT", "", "", "30", "", "NULLABLE", "NON_REQUIRED", "")
    arcpy.CalculateField_management(memOwner, "mailCountry", "\"UNITED STATES OF AMERICA\"", "PYTHON_9.3")

    arcpy.FeatureToPoint_management(memOwner, memOwnerPts, "INSIDE")
    
    # Renaming field names to what they map to in Accela.
    renameFields(memOwnerPts, ownerFields)

    try:
        arcpy.CopyFeatures_management(memOwnerPts, outputOwner)

    except arcpy.ExecuteError:
        # Copying features didn't work on first try. Trying to get exclusive schema lock to retry.
        # Disabling connectivity to database
        arcpy.AcceptConnections(outSDE, False)
        # Disconnecting all users
        arcpy.DisconnectUser(outSDE, 'ALL')
        arcpy.CopyFeatures_management(memOwnerPts, outputOwner)
        arcpy.AcceptConnections(outSDE, True)
    finally:
        arcpy.AcceptConnections(outSDE, True)