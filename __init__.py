# ***** BEGIN GPL LICENSE BLOCK *****
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software Foundation,
# Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
# ***** END GPL LICENCE BLOCK *****

# <pep8 compliant>

bl_info = {
    "name": "Powerlib",
    "author": "Inês Almeida, Francesco Siddi, Olivier Amrein, Dalai Felinto",
    "version": (2, 0, 0),
    "blender": (2, 78, 0),
    "location": "View3D > Tool Shelf (T)",
    "description": "todo",
    "warning": "",
    "wiki_url": "http://wiki.blender.org/index.php/Extensions:2.6/Py/"
                "Scripts/Workflow/-todo-create-new-documentation-page!",
    "category": "Workflow",
}

import os
import json

import bpy
from bpy.app.handlers import persistent
from bpy.types import (
    Operator,
    Menu,
    Panel,
    UIList,
    PropertyGroup,
)
from bpy.props import (
    BoolProperty,
    IntProperty,
    StringProperty,
    EnumProperty,
    CollectionProperty,
    PointerProperty,
)


VERBOSE = False # enable this for debugging

def debug_print(*args):
    """Print debug messages"""
    if VERBOSE:
        print(*args)


# Data Structure ##############################################################

# A powerlib library is structured as a series of collections of assets.
# An asset has a set of components which are organized by type.
# eg. the library defined in XXX has the Collections "Characters" and "Props"
#     the collection "Characters" contains the assets "Boris" and "Agent327"
#     an asset has one or more components of type "instance_groups"
#     which consist of a path to the blend file and the name of the group to instance

runtime_vars = {}
class ReadState:
    NotLoaded, NoFile, FilePathInvalid, FileContentInvalid, EmptyLib, AllGood = range(6)
runtime_vars["read_state"] = ReadState.NotLoaded
class SaveState:
    HasUnsavedChanges, AllSaved = range(2)
runtime_vars["save_state"] = SaveState.AllSaved


enum_component_type = EnumProperty(
    items=(
        ('INSTANCE_GROUPS', "Instance Groups", "", 'EMPTY_DATA', 0),
        #('NONINSTANCE_GROUPS', "Non Instance Groups", "", 'GROUP', 1),
        ('GROUP_REFERENCE_OBJECTS', "Group Reference Objects", "", 'OBJECT_DATA', 2),
    ),
    default='INSTANCE_GROUPS',
    name="Component Type",
    description="Type of an asset component",
)


def enum_item_name_icon(enum, value):
    """Return the item name and icon of an enum
    """
    prop, settings = enum

    for item in settings['items']:
        if item[0] == value:
            return item[1], item[3]
    return "Error", 'ERROR'


class ComponentItem(PropertyGroup):
    name = StringProperty()


class Component(PropertyGroup):
    def update_filepath_rel(self, context):
        """Updates the filepath property after we picked a new value for
        filepath_rel via a file browser.
        """
        #~ self.group = None
        self.groups.clear()

        if self.filepath_rel == '':
            return
        # TODO: ensure path is valid
        # Make path relative to the library
        from . import linking
        import importlib
        importlib.reload(linking)

        fp_rel_to_lib = linking.relative_path_to_lib(self.filepath_rel)
        debug_print('Updating library link to {}'.format(fp_rel_to_lib))
        self.filepath = fp_rel_to_lib

        cache_key = self.filepath
        if self.filepath_rel == '//' + os.path.basename(bpy.data.filepath):
            for g in bpy.data.groups:
                if g.library:
                    continue
                self.groups.add().name = g.name
        else:
            filepath = bpy.path.relpath(self.absolute_filepath)
            with bpy.data.libraries.load(filepath) as (data_from, data_to):
                for gname in data_from.groups:
                    self.groups.add().name = gname

    id = StringProperty(
        name="Name",
        description="Name for this component, eg. the name of a group",
    )

    groups = CollectionProperty(type=ComponentItem)

    filepath = StringProperty(
        name="File path",
        description="Path to the blend file which holds this data relative to the library",
        subtype='FILE_PATH',
    )

    filepath_rel = StringProperty(
        name="Relative file path",
        description="Path to the blend file which holds this data relative from the current file",
        subtype='FILE_PATH',
        update=update_filepath_rel,
    )

    @property
    def absolute_filepath(self):
        library_path = os.path.dirname(
            bpy.path.abspath(bpy.context.scene['lib_path']))
        abspath = os.path.join(library_path, self.filepath)
        normpath = os.path.normpath(abspath)
        if os.path.isfile(normpath):
            return normpath
        else:
            # raise IOError('File {} not found'.format(normpath))
            debug_print('IOError: File {} not found'.format(normpath))


class ComponentsList(PropertyGroup):
    """A set of components of a certain type that build an asset
    example types: (groups, group_reference_objects, scripts).
    """
    component_type = enum_component_type

    components = CollectionProperty(
        name="Components",
        description="List of components of this type",
        type=Component,
    )
    active_component = IntProperty(
        name="Selected Component",
        description="Currently selected component of this type",
    )

    @staticmethod
    def getComponentType(name):
        lookup = {
            'instance_groups': 'INSTANCE_GROUPS',
            'noninstance_groups': 'NONINSTANCE_GROUPS',
            'group_reference_objects': 'GROUP_REFERENCE_OBJECTS',
        }
        value = lookup.get(name)
        if value is None:
            raise Exception("Component type not supported: {0}".format(name))

        return value


class AssetItem(PropertyGroup):
    components_by_type = CollectionProperty(
        name="Components by Type",
        type=ComponentsList,
    )


class AssetCollection(PropertyGroup):
    active_asset = IntProperty(
        name="Selected Asset",
        description="Currently selected asset",
    )
    assets = CollectionProperty(
        name="Assets",
        description="List of assets in this collection",
        type=AssetItem,
    )


class PowerProperties(PropertyGroup):
    is_edit_mode = BoolProperty(
        name="Is in Edit Mode",
        description="Toggle for Edit/Selection mode",
        default=False,
    )

    collections = CollectionProperty(
        name="PowerLib Collections",
        description="List of Asset Collections in the active library",
        type=AssetCollection,
    )

    active_col = StringProperty(
        name="Active Collection",
        description="Currently selected collection",
    )


# Operators ###################################################################

class ColRequiredOperator(Operator):
    @classmethod
    def poll(self, context):
        wm = context.window_manager
        active_col = wm.powerlib_props.active_col
        return (active_col
            and wm.powerlib_props.collections[active_col])

    @staticmethod
    def name_new_item(container, default_name):
        if default_name not in container:
            return default_name
        else:
            sorted_container = []
            for a in container:
                if a.name.startswith(default_name + "."):
                    index = a.name[len(default_name) + 1:]
                    if index.isdigit():
                        sorted_container.append(index)
            sorted_container = sorted(sorted_container)
            min_index = 1
            for num in sorted_container:
                num = int(num)
                if min_index < num:
                    break
                min_index = num + 1
            return"{:s}.{:03d}".format(default_name, min_index)


class ColAndAssetRequiredOperator(ColRequiredOperator):
    @classmethod
    def poll(self, context):
        if super().poll(context):
            wm = context.window_manager
            col = wm.powerlib_props.collections[wm.powerlib_props.active_col]
            return (col.active_asset < len(col.assets)
                and col.active_asset >= 0)
        return False


class ASSET_OT_powerlib_reload_from_json(Operator):
    bl_idname = "wm.powerlib_reload_from_json"
    bl_label = "Reload from JSON"
    bl_description = "Loads the library from the JSON file. Overrides non saved local edits!"
    bl_options = {'UNDO', 'REGISTER'}

    @classmethod
    def poll(self, context):
        return True

    def execute(self, context):
        from . import linking
        import importlib
        importlib.reload(linking)

        wm = context.window_manager

        wm.powerlib_props.collections.clear()
        wm.powerlib_props.active_col = ""
        runtime_vars["save_state"] = SaveState.AllSaved

        # Load single json library file

        library_path = bpy.path.abspath(context.scene.lib_path)
        debug_print("PowerLib2: Reading JSON library file from %s" % library_path)

        if not library_path:
            debug_print("PowerLib2: ... no library path specified!")
            runtime_vars["read_state"] = ReadState.NoFile
            return {'FINISHED'}

        if not os.path.exists(library_path):
            debug_print("PowerLib2: ... library filepath invalid!")
            runtime_vars["read_state"] = ReadState.FilePathInvalid
            return {'FINISHED'}

        library = {}

        with open(library_path) as data_file:
            try:
                library = json.load(data_file)
            except (json.decoder.JSONDecodeError, KeyError, ValueError):
                # malformed json data
                debug_print("PowerLib2: ... JSON content is empty or malformed!")
                runtime_vars["read_state"] = ReadState.FileContentInvalid
                return {'FINISHED'}

        # Collections, eg. Characters
        for collection_name in library:
            asset_collection_prop = wm.powerlib_props.collections.add()
            asset_collection_prop.name = collection_name

            # Assets, eg. Boris
            collection = library[collection_name]
            for asset_name in sorted(collection.keys()):
                asset_json = collection[asset_name]

                asset_prop = asset_collection_prop.assets.add()
                asset_prop.name = asset_name

                # Component Types, eg. instance_groups
                for ctype_name, ctype_components in asset_json.items():
                    ctype_prop = asset_prop.components_by_type.add()
                    ctype_prop.name = ctype_name
                    ctype_prop.component_type = ctype_prop.getComponentType(ctype_name)

                    # Individual components of this type, each with filepath and name
                    for filepath, name in ctype_components:
                        component_prop = ctype_prop.components.add()
                        component_prop.name = name
                        component_prop.id = name
                        component_prop.filepath = filepath
                        absolute_filepath = component_prop.absolute_filepath
                        if absolute_filepath:
                            bf_rel_fp = linking.relative_path_to_file(component_prop.absolute_filepath)
                        else:
                            bf_rel_fp = ''
                        component_prop.filepath_rel = bf_rel_fp

        if library:
            # Assign some collection by default (dictionaries are unordered)
            wm.powerlib_props.active_col = next(iter(library.keys()))

            runtime_vars["read_state"] = ReadState.AllGood
        else:
            runtime_vars["read_state"] = ReadState.EmptyLib

        debug_print("PowerLib2: ... looks good!")

        return {'FINISHED'}


class ASSET_OT_powerlib_save_to_json(Operator):
    bl_idname = "wm.powerlib_save_to_json"
    bl_label = "Save to JSON"
    bl_description = "Saves the edited library to the json file. Overrides the previous content!"
    bl_options = {'UNDO', 'REGISTER'}

    @classmethod
    def poll(self, context):
        return True

    def execute(self, context):
        wm = context.window_manager

        # Save properties to the JSON library file

        library_path = bpy.path.abspath(context.scene.lib_path)
        debug_print("PowerLib2: Saving JSON library to file %s" % library_path)

        if not library_path or not os.path.exists(library_path):
            debug_print("PowerLib2: ... invalid filepath! Could not save!")
            self.report({'ERROR'}, "Invalid path! Could not save!")
            return {'FINISHED'}

        collections_json_dict = {}

        # Collections, eg. Characters
        for collection in wm.powerlib_props.collections:
            assets_json_dict = {}

            # Assets, eg. Boris
            for asset_name, asset_body in collection.assets.items():
                comps_by_type_json_dict = {}

                # Component Types, eg. instance_groups
                for comp_type_name, comp_type_body in asset_body.components_by_type.items():
                    comps_by_type_json_dict[comp_type_name] = []

                    # Individual components of this type, each with filepath and name
                    for i in comp_type_body.components:
                        comps_by_type_json_dict[comp_type_name].append([
                            i.filepath, i.id
                        ])

                assets_json_dict[asset_name] = comps_by_type_json_dict
            collections_json_dict[collection.name] = assets_json_dict

        with open(library_path, 'w') as data_file:
            json.dump(collections_json_dict, data_file, indent=4, sort_keys=True,)

        runtime_vars["save_state"] = SaveState.AllSaved
        debug_print("PowerLib2: ... no errors!")
        return {'FINISHED'}


class ASSET_OT_powerlib_collection_rename(ColRequiredOperator):
    bl_idname = "wm.powerlib_collection_rename"
    bl_label = "Rename Collection"
    bl_description = "Rename the asset collection"
    bl_options = {'UNDO', 'REGISTER'}

    name = StringProperty(name="Name", description="Name of the collection")

    def invoke(self, context, event):
        wm = context.window_manager
        # fill in the field with the current value
        self.name = wm.powerlib_props.collections[wm.powerlib_props.active_col].name
        return wm.invoke_props_dialog(self)

    def execute(self, context):
        wm = context.window_manager
        col = wm.powerlib_props.collections[wm.powerlib_props.active_col]
        col.name = self.name
        wm.powerlib_props.active_col = self.name

        runtime_vars["save_state"] = SaveState.HasUnsavedChanges
        return {'FINISHED'}


class ASSET_OT_powerlib_collection_add(Operator):
    bl_idname = "wm.powerlib_collection_add"
    bl_label = "Add Collection"
    bl_description = "Add a new asset collection"
    bl_options = {'UNDO', 'REGISTER'}

    name = StringProperty(name="Name", description="Name of the collection")

    def invoke(self, context, event):
        wm = context.window_manager
        return wm.invoke_props_dialog(self)

    def execute(self, context):
        wm = context.window_manager
        col = wm.powerlib_props.collections.add()
        col.name = self.name
        wm.powerlib_props.active_col = self.name
        runtime_vars["save_state"] = SaveState.HasUnsavedChanges
        return {'FINISHED'}


class ASSET_OT_powerlib_collection_del(ColRequiredOperator):
    bl_idname = "wm.powerlib_collection_del"
    bl_label = "Delete Collection"
    bl_description = "Delete the selected asset collection"
    bl_options = {'UNDO', 'REGISTER'}

    def execute(self, context):
        wm = context.window_manager
        idx = wm.powerlib_props.collections.find(wm.powerlib_props.active_col)
        wm.powerlib_props.collections.remove(idx)
        wm.powerlib_props.active_col = ""
        runtime_vars["save_state"] = SaveState.HasUnsavedChanges
        return {'FINISHED'}


class ASSET_OT_powerlib_assetitem_add(ColRequiredOperator):
    bl_idname = "wm.powerlib_assetitem_add"
    bl_label = "Add Asset"
    bl_description = "Add a new asset to the selected collection"
    bl_options = {'UNDO', 'REGISTER'}

    def execute(self, context):
        wm = context.window_manager
        col = wm.powerlib_props.collections[wm.powerlib_props.active_col]

        asset = col.assets.add()

        # naming
        asset.name = self.name_new_item(col.assets, "NewAsset")

        # select newly created asset
        col.active_asset = len(col.assets) - 1

        runtime_vars["save_state"] = SaveState.HasUnsavedChanges
        return {'FINISHED'}


class ASSET_OT_powerlib_assetitem_del(ColAndAssetRequiredOperator):
    bl_idname = "wm.powerlib_assetitem_del"
    bl_label = "Delete Asset"
    bl_description = "Delete the selected asset"
    bl_options = {'UNDO', 'REGISTER'}

    def execute(self, context):
        wm = context.window_manager
        col = wm.powerlib_props.collections[wm.powerlib_props.active_col]

        col.assets.remove(col.active_asset)

        # change currently active asset
        num_assets = len(col.assets)
        if (col.active_asset > (num_assets - 1) and num_assets > 0):
            col.active_asset = num_assets - 1

        runtime_vars["save_state"] = SaveState.HasUnsavedChanges
        return {'FINISHED'}


class ASSET_OT_powerlib_component_add(ColAndAssetRequiredOperator):
    bl_idname = "wm.powerlib_component_add"
    bl_label = "Add Asset Component"
    bl_description = "Add a new component to the selected asset"
    bl_options = {'UNDO', 'REGISTER'}

    component_type = enum_component_type
    needs_select = BoolProperty(default=False, options={'HIDDEN'})

    def invoke(self, context, event):
        wm = context.window_manager
        if self.needs_select:
            self.needs_select = False
            return wm.invoke_props_dialog(self)
        else:
            return self.execute(context)

    def execute(self, context):
        wm = context.window_manager

        asset_collection = wm.powerlib_props.collections[wm.powerlib_props.active_col]
        active_asset = asset_collection.assets[asset_collection.active_asset]

        # create container for type if it does not exist yet
        components_of_type = active_asset.components_by_type.get(self.component_type.lower())
        if components_of_type is None:
            components_of_type = active_asset.components_by_type.add()
            components_of_type.name = self.component_type.lower()
            components_of_type.component_type = self.component_type

        component = components_of_type.components.add()

        # naming
        component.name = self.name_new_item(components_of_type.components, "NewComponent")

        # select newly created component
        components_of_type.active_component = len(components_of_type.components) - 1

        runtime_vars["save_state"] = SaveState.HasUnsavedChanges
        return {'FINISHED'}


class ASSET_OT_powerlib_component_del(ColAndAssetRequiredOperator):
    bl_idname = "wm.powerlib_component_del"
    bl_label = "Delete Asset Component"
    bl_description = "Delete the selected asset component"
    bl_options = {'UNDO', 'REGISTER'}

    component_type = enum_component_type

    def execute(self, context):
        wm = context.window_manager

        asset_collection = wm.powerlib_props.collections[wm.powerlib_props.active_col]
        active_asset = asset_collection.assets[asset_collection.active_asset]

        # ignore if container for type does not exist
        components_of_type = active_asset.components_by_type.get(self.component_type.lower())
        if components_of_type is None:
            return {'FINISHED'}

        components_of_type.components.remove(components_of_type.active_component)

        num_components = len(components_of_type.components)
        # if this component type list is empty, delete
        if num_components == 0:
            idx = active_asset.components_by_type.find(self.component_type.lower())
            active_asset.components_by_type.remove(idx)
        # change currently active component
        elif (components_of_type.active_component > (num_components - 1) and num_components > 0):
            components_of_type.active_component = num_components - 1

        runtime_vars["save_state"] = SaveState.HasUnsavedChanges
        return {'FINISHED'}


class AssetFiles():
    def __init__(self):
        self._components = {}
        self._files = {}

    @staticmethod
    def get_nested_array(_dict, key, array):
        if key not in _dict:
            _dict[key] = array()
        return _dict[key]

    def get_component(self, component_type):
        return self.get_nested_array(self._components, component_type, dict)

    def add(self, component_type, filepath, _id):
        """Populate the dictionary of lists"""
        _component = self.get_component(component_type)
        _file = self.get_nested_array(_component, filepath, list)
        _file.append(_id)

    def process(self):
        """handle the importing"""
        callbacks = {
                'GROUP_REFERENCE_OBJECTS': linking.load_group_reference_objects,
                'INSTANCE_GROUPS': linking.load_instance_groups,
                }

        for _component, _files in self._components.items():
            callback = callbacks.get(_component)

            assert callback, "Component \"{0}\" not supported".format(_component)

            for _file, ids in _files.items():
                callback(_file, ids)


class ASSET_OT_powerlib_link_in_component(ColAndAssetRequiredOperator):
    bl_idname = "wm.powerlib_link_in_component"
    bl_label = "TODO"
    bl_description = "TODO"
    bl_options = {'UNDO', 'REGISTER'}

    index = IntProperty(
            default=-1,
            options={'HIDDEN', 'SKIP_SAVE'},
            )

    def execute(self, context):
        from . import linking
        if "bpy" in locals():
            import importlib
            importlib.reload(linking)

        wm = context.window_manager

        asset_collection = wm.powerlib_props.collections[wm.powerlib_props.active_col]

        if self.index == -1:
            active_asset = asset_collection.assets[asset_collection.active_asset]
        else:
            active_asset = asset_collection.assets[self.index]

        debug_print('Linking in {}'.format(active_asset.name))

        files = AssetFiles()

        for component_list in active_asset.components_by_type:
            component_type = component_list.component_type

            for component in component_list.components:
                files.add(component_type, component.absolute_filepath, component.id)

        files.process()

        return {'FINISHED'}


# Panel #######################################################################

class ASSET_UL_asset_components(UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        is_edit_mode = context.window_manager.powerlib_props.is_edit_mode
        col = layout.split()
        col.enabled = is_edit_mode
        col.prop(item, "filepath_rel", text="", emboss=is_edit_mode)
        col.prop_search(item, "id", item, "groups", text="")


class ASSET_UL_collection_assets(UIList):
    def draw_item(self, context, layout, data, set, icon, active_data, active_propname, index):
        # layout.prop(set, "name", text="", icon='LINK_BLEND', emboss=False)
        is_edit_mode = context.window_manager.powerlib_props.is_edit_mode
        col = layout.split()
        col.prop(set, "name", text="", icon='LINK_BLEND', emboss=False)
        if is_edit_mode:
            return
        col = layout.split()
        col.enabled = True
        monkey = col.operator("wm.powerlib_link_in_component", text="", icon='MESH_MONKEY')
        monkey.index = index


class ASSET_PT_powerlib(Panel):
    bl_label = 'Powerlib'       # panel section name
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'TOOLS'
    bl_category = 'Powerlib'    # tab name

    @classmethod
    def poll(cls, context):
        # restrict availability?
        return True #(context.mode == 'OBJECT')

    def draw_header(self, context):
        wm = context.window_manager

        row = self.layout.row(align=True)
        row.prop(wm.powerlib_props, "is_edit_mode",
            text="",
            icon='GREASEPENCIL' if wm.powerlib_props.is_edit_mode else 'HAND')
        row.operator("wm.powerlib_reload_from_json", text="", icon='FILE_REFRESH')

    def draw(self, context):
        wm = context.window_manager
        scene = context.scene

        is_edit_mode = wm.powerlib_props.is_edit_mode
        layout = self.layout

        # Setting for the JSON library path

        if is_edit_mode:
            row = layout.row()
            row.prop(scene, "lib_path", text="Library Path")
            layout.separator()

        # Fail report for library loading

        read_state = runtime_vars["read_state"]

        if (read_state != ReadState.AllGood
            and not (read_state == ReadState.EmptyLib and is_edit_mode)):

            row = layout.row()
            row.alignment = 'CENTER'
            if (read_state == ReadState.NotLoaded or read_state == ReadState.NoFile):
                if is_edit_mode:
                    row.label("No library path loaded", icon='ERROR')
                else:
                    row.alignment = 'EXPAND'
                    row.label("Choose a library path:")
                    row = layout.row()
                    row.prop(scene, "lib_path", text="")
            elif (read_state == ReadState.FilePathInvalid):
                if not is_edit_mode:
                    row.alignment = 'EXPAND'
                    row.label("Choose a library path:")
                    row = layout.row()
                    row.prop(scene, "lib_path", text="")
                    row = layout.row()
                row.label("Can not find a library in the given path", icon='ERROR')
            elif (read_state == ReadState.FileContentInvalid):
                row.label("The library is empty or corrupt!", icon='ERROR')
            elif (read_state == ReadState.EmptyLib and not is_edit_mode):
                row.label("The chosen library is empty")

            return

        # Category selector

        row = layout.row(align=True)

        row.prop_search(
            wm.powerlib_props, "active_col",  # Currently active
            wm.powerlib_props, "collections", # Collection to search
            text="", icon="EXPORT"    # UI icon and label
        )
        if is_edit_mode:
            row.operator("wm.powerlib_collection_rename", text="", icon='OUTLINER_DATA_FONT')
            row.operator("wm.powerlib_collection_add", text="", icon='ZOOMIN')
            row.operator("wm.powerlib_collection_del", text="", icon='ZOOMOUT')

        # UI List with the assets of the selected category

        row = layout.row()
        if (wm.powerlib_props.active_col):
            asset_collection = wm.powerlib_props.collections[wm.powerlib_props.active_col]
            row.template_list(
               "ASSET_UL_collection_assets", "", # type and unique id
                asset_collection, "assets",      # pointer to the CollectionProperty
                asset_collection, "active_asset",# pointer to the active identifier
                rows=6,
            )
            # add/remove/specials UI list Menu
            if is_edit_mode:
                col = row.column(align=True)
                col.operator("wm.powerlib_assetitem_add", icon='ZOOMIN', text="")
                col.operator("wm.powerlib_assetitem_del", icon='ZOOMOUT', text="")
                #col.menu("ASSET_MT_powerlib_assetlist_specials", icon='DOWNARROW_HLT', text="")
        else:
            row.enabled = False
            row.label("Choose an Asset Collection!")

        # Properties and Components of this Asset

        if wm.powerlib_props.active_col:
            layout.separator()

            if asset_collection.assets:
                active_asset = asset_collection.assets[asset_collection.active_asset]

                for components_of_type in active_asset.components_by_type:
                    row = layout.row()
                    name, icon = enum_item_name_icon(enum_component_type, components_of_type.component_type)
                    row.label(text=name, icon=icon)

                    row = layout.row()
                    row.template_list(
                        "ASSET_UL_asset_components",           # type
                        "components_of_type.component_type",   # unique id
                        components_of_type, "components",      # pointer to the CollectionProperty
                        components_of_type, "active_component",# pointer to the active identifier
                        rows=2,
                    )
                    # add/remove/specials UI list Menu
                    if is_edit_mode:
                        col = row.column(align=True)
                        col.operator("wm.powerlib_component_add", icon='ZOOMIN', text="").component_type = components_of_type.component_type
                        col.operator("wm.powerlib_component_del", icon='ZOOMOUT', text="").component_type = components_of_type.component_type


        if is_edit_mode:
            layout.separator()
            row = layout.row()
            row.operator("wm.powerlib_component_add", icon='ZOOMIN').needs_select = True

        # Save

        if is_edit_mode:
            layout.separator()
            row = layout.row()
            row.operator("wm.powerlib_save_to_json",
                icon='ERROR' if runtime_vars["save_state"] == SaveState.HasUnsavedChanges else 'FILE_TICK')


# Registry ####################################################################

classes = (
    ComponentItem,
    Component,
    ComponentsList,
    AssetItem,
    AssetCollection,
    PowerProperties,
    ASSET_UL_asset_components,
    ASSET_UL_collection_assets,
    ASSET_PT_powerlib,
    ASSET_OT_powerlib_reload_from_json,
    ASSET_OT_powerlib_save_to_json,
    ASSET_OT_powerlib_collection_rename,
    ASSET_OT_powerlib_collection_add,
    ASSET_OT_powerlib_collection_del,
    ASSET_OT_powerlib_assetitem_add,
    ASSET_OT_powerlib_assetitem_del,
    ASSET_OT_powerlib_component_add,
    ASSET_OT_powerlib_component_del,
    ASSET_OT_powerlib_link_in_component,
)


def powerlib_lib_path_update_cb(self, context):
    debug_print("PowerLib2: Loading Add-on and Library")
    bpy.ops.wm.powerlib_reload_from_json()


def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.types.WindowManager.powerlib_props = PointerProperty(
        name="Powerlib Add-on Properties",
        description="Properties and data used by the Powerlib Add-on",
        type=PowerProperties,
    )

    bpy.types.Scene.lib_path = StringProperty(
        name="Powerlib Add-on Library Path",
        description="Path to a PowerLib JSON file",
        subtype='FILE_PATH',
        update=powerlib_lib_path_update_cb,
    )


def unregister():
    del bpy.types.Scene.lib_path
    del bpy.types.WindowManager.powerlib_props

    for cls in classes:
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
