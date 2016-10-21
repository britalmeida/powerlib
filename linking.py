import os
import bpy

def treat_ob(ob, grp=None):
    print('Processing {}'.format(ob.name))
    try:
        existing = bpy.data.objects[ob.name, None]
    except KeyError:
        print('Not yet in Blender, just linking to scene.')
        # only for objects not yet in the file:
        if ob.name not in bpy.context.scene.objects:
            bpy.context.scene.objects.link(ob)
    else:
        print('Updating {}'.format(ob.name))
        # when an object already exists:
        # - find local version
        # - user_remap() it
        existing.user_remap(ob)
        existing.name = '(PRE-SPLODE LOCAL) %s' % existing.name
        bpy.data.objects.remove(existing)

    # for all:
    # make local
    override = bpy.context.copy()
    override['selected_objects'] = [ob]
    bpy.ops.object.make_local(override)
    grp.objects.link(ob)



def load_group_reference_objects(filepath, group_name):
    # We load one group at a time
    print('Loading group {}'.format(group_name))
    common_path = os.path.commonprefix([bpy.data.filepath, filepath])
    rel_path = os.path.relpath(filepath, common_path)
    # TODO: make this better. Should be a blender stype relpath
    rel_path = '//' + rel_path
    # Road a object scene we know the name of.
    with bpy.data.libraries.load(rel_path, link=True) as (data_from, data_to):
        data_to.groups = [group_name]

    for group in data_to.groups:
        print('Handling group {}'.format(group.name))
        ref_group_name = '__REF{}'.format(group.name)
        if ref_group_name in bpy.data.groups:
            object_names_from = [ob.name for ob in group.objects]
            object_names_to = [ob.name for ob in bpy.data.groups[ref_group_name].objects]
            object_names_diff = list(set(object_names_to) - set(object_names_from))
            # Delete removed objects
            for ob in object_names_diff:
                bpy.data.objects[ob].select = True
                bpy.ops.object.delete()
        else:
            bpy.ops.group.create(name=ref_group_name)
        for ob in group.objects:
            treat_ob(ob, bpy.data.groups[ref_group_name])
