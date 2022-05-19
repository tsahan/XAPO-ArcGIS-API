# Description: Generates XAPO data and stores it in the SQL Server.
# Requirements: Python 2.7, arcpy
# Variables are skipped due to confidentiality.

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

    SDEFolder = 
    outSDE = 

    landRecordsSDE = 
    propertiesSDE = 
    zonesBoundariesSDE = 

    # Output Locations
    outputAddress = 
    outputOwner = 
    outputParcel = 

    # Read data
    parcels = 
    councilDistricts = 
    inspectorAreas = 
    SBAddrPts = 
    countyAddrPts = 
    cityLimits = 
    contEnforcemnt = 

    arcpy.env.overwriteOutput = True
    
    # Generates owner layer
    COSBDebug.log("Generating owner layer")
    ownerLayer.ownerLayer(parcels, outputOwner, outSDE)  
    # Generates parcel layer
    COSBDebug.log("Generating parcel layer")
    parcelLayer.parcelLayer(parcels, councilDistricts, inspectorAreas, contEnforcemnt, outputParcel, outSDE)
    # Generates address layer
    COSBDebug.log("Generating address layer")
    addressLayer.addressLayer(SBAddrPts, countyAddrPts, parcels, cityLimits, outputAddress, outSDE)

main()