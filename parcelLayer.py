import arcpy
from misc import dropExtraFields, renameFields

def parcelLayer(memPDI, outputParcel, outSDE):
    parcelFields = {
        "REALIMPROV" : "improvedValue",
        "Num" : "InspectionDistrict",
        "REALLANDVA" : "landValue",
        "LEGALDESCR" : "legalDesc",
        "MAPREFEREN" : "mapRef",
        "PARCELSTAT" : "parcelNumber",
        "ACERAGE" : "parcelArea",
        "InspectorAreas" : "EnvironmentalAreas",
        "InspectorAreas_1" : "HousingAreas"
    }

    dropExtraFields(memPDI, parcelFields)
    renameFields(memPDI, parcelFields)

    try:
        arcpy.CopyFeatures_management(memPDI, outputParcel)

    except arcpy.ExecuteError:
        # Copying features didn't work on first try. Trying to get exclusive schema lock to retry.
        # Disabling connectivity to database
        arcpy.AcceptConnections(outSDE, False)
        # Disconnecting all users
        arcpy.DisconnectUser(outSDE, 'ALL')
        arcpy.CopyFeatures_management(memPDI, outputParcel)
        arcpy.AcceptConnections(outSDE, True)
    finally:
        arcpy.AcceptConnections(outSDE, True)