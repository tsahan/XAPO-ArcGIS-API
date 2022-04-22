import arcpy
# Remove all output fields you don't want.
def dropExtraFields(loc, passFields):
    passTypes = ["OID", "Geometry", "Guid"]
    notToDropFields = ["SHAPE", "OBJECTID", "SHAPE.STLength()", "SHAPE.STArea()"  "SHAPE.STArea()", "PARCELID"]
    dropFields = []
    for field in arcpy.ListFields(loc):
        if field.name not in passFields.keys() and field.type not in passTypes and field.name not in notToDropFields:
            dropFields.append(field.name)
    arcpy.DeleteField_management(loc, dropFields)

# Change field names to better align with the APO mapping
def renameFields(loc, passFields):
    for field in arcpy.ListFields(loc):
        if field.name in passFields.keys():
            arcpy.management.AlterField(loc, field.name, passFields[field.name])
    print "Renamed fields of {}".format(str(loc))