import os
import bpy

def relative_path_to_file(filepath):
    """Makes a path relative to the current file"""
    common_path = os.path.commonprefix([bpy.data.filepath, filepath])
    rel_path = os.path.relpath(filepath, common_path)
    # TODO: make this better. Should be a blender style relpath.
    if rel_path == '.':
        rel_path = os.path.basename(filepath)
    rel_path = '//' + rel_path
    # TODO: handle the case where path is absolute
    return rel_path


def absolute_path_from_file(rel_filepath):
    if rel_filepath.startswith('//'):
        rel_filepath = rel_filepath[2:]
    normpath = os.path.normpath(rel_filepath)
    dirname = os.path.dirname(bpy.data.filepath)
    filepath = os.path.join(dirname, normpath)
    return filepath


def relative_path_to_lib(filepath):
    """Makes a path relative to the current library"""
    filepath = absolute_path_from_file(filepath)
    libpath = os.path.dirname(
        absolute_path_from_file(bpy.context.scene['lib_path']))
    rel_path = os.path.relpath(filepath, libpath)
    # TODO: handle the case where path is absolute
    return rel_path


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
    rel_path = make_library_path_relative(filepath)
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
