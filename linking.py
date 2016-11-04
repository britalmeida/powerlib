import os
import bpy

def relative_path_to_file(filepath):
    """Makes a path relative to the current file"""
    return bpy.path.relpath(filepath)


def absolute_path_from_file(rel_filepath):
    return bpy.path.abspath(rel_filepath)


def relative_path_to_lib(filepath):
    """Makes a path relative to the current library"""
    filepath = absolute_path_from_file(filepath)
    libpath = os.path.dirname(
        absolute_path_from_file(bpy.context.scene['lib_path']))
    rel_path = os.path.relpath(filepath, libpath)
    return rel_path


def make_local(ob):
    # for all:
    # make local
    override = bpy.context.copy()
    override['selected_objects'] = [ob]
    bpy.ops.object.make_local(override)


def treat_ob(ob, grp):
    """Remap existing ob to the new ob"""
    print('Processing {}'.format(ob.name))
    try:
        existing = bpy.data.objects[ob.name, None]
    except KeyError:
        print('Not yet in Blender, just linking to scene.')
        # only for objects not yet in the file:
        if ob.name not in bpy.context.scene.objects:
            bpy.context.scene.objects.link(ob)

        # after we make it local the original ob is no longer the one we are looking for
        make_local(ob)

        # try to get the new objects, sometimes there won't be one
        for o in bpy.data.objects:
            if o != ob and o.name == ob.name:
                ob = o
                break

    else:
        print('Updating {}'.format(ob.name))
        # when an object already exists:
        # - find local version
        # - user_remap() it
        existing.user_remap(ob)
        existing.name = '(PRE-SPLODE LOCAL) %s' % existing.name
        # Preserve visible or hidden state
        ob.hide = existing.hide
        # Preserve animation (used to place the instance in the scene)
        if existing.animation_data:
            ob.animation_data_create()
            ob.animation_data.action = existing.animation_data.action
        bpy.data.objects.remove(existing)

        make_local(ob)

    print('GRP: ', grp.name)
    grp.objects.link(ob)


def load_group_reference_objects(filepath, group_name):
    # We load one group at a time
    print('Loading group {}'.format(group_name))
    rel_path = relative_path_to_file(filepath)
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
