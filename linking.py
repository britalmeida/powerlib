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


def bottom_up_from_idblock(idblock):
    """Generator, yields datablocks from the bottom (i.e. uses nothing) upward.

    Stupid in that it doesn't detect cycles yet.

    :param idblock: the idblock whose users to yield.
    """

    visited = set()

    def visit(idblock):
        # Prevent visiting the same idblock multiple times
        if idblock in visited:
            return
        visited.add(idblock)

        user_map = bpy.data.user_map([idblock])
        # There is only one entry here, for the idblock we requested.
        for user in user_map[idblock]:
            yield from visit(user)
        yield idblock

    yield from visit(idblock)


def make_local(ob):
    # make local like a boss (using the patch from Sybren Stuvel)
    for idblock in bottom_up_from_idblock(ob):

        if idblock.library is None:
            # Already local
            continue

        print('Should make %r local: ' % idblock)
        print('   - result: %s' % idblock.make_local(clear_proxy=False))

        # this shouldn't happen, but it does happen :/
        if idblock.library:
            pass


def treat_ob(ob, grp):
    """Remap existing ob to the new ob"""
    ob_name = ob.name
    print('Processing {}'.format(ob_name))

    try:
        existing = bpy.data.objects[ob_name, None]

    except KeyError:
        print('Not yet in Blender, just linking to scene.')
        bpy.context.scene.objects.link(ob)

        make_local(ob)
        ob = bpy.data.objects[ob_name, None]

        print('GRP: ', grp.name)
        grp.objects.link(ob)

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


def load_group_reference_objects(filepath, group_names):
    # We load one group at a time
    print('Loading groups {} : {}'.format(filepath, group_names))
    rel_path = relative_path_to_file(filepath)

    # Road a object scene we know the name of.
    with bpy.data.libraries.load(rel_path, link=True) as (data_from, data_to):
        data_to.groups = group_names

    data = {}
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

        # store all the objects that are in the group
        data[bpy.data.groups[ref_group_name]] = [ob for ob in group.objects]

        # remove the groups
        bpy.data.groups.remove(group, do_unlink=True)

    # add the new objects and make them local
    process_group_reference_objects(data)


def process_group_reference_objects(data):
    for group, objects in data.items():
        for ob in objects:
            treat_ob(ob, group)


def load_instance_groups(filepath, group_names):
    print('Loading groups {} : {}'.format(filepath, group_names))
    rel_path = relative_path_to_file(filepath)

    # Road a object scene we know the name of.
    with bpy.data.libraries.load(rel_path, link=True) as (data_from, data_to):
        data_to.groups = group_names

    scene = bpy.context.scene
    objects = []
    for group in group_names:
        ob = bpy.data.objects.new(group.name, None)
        ob.dupli_type = 'GROUP'
        ob.dupli_group = group

        scene.objects.link(ob)
        objects.append(ob)
    return objects

