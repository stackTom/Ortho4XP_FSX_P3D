from O4_Geo_Utils import gtile_to_wgs84
import O4_ESP_Globals
import os
import O4_File_Names as FNAMES
import O4_Config_Utils
import subprocess
from fast_image_mask import *
import glob
from queue import Queue
from threading import Thread
import math
import O4_Imagery_Utils

# TODO: use os.path.join instead of os.sep and concatenation
# TODO: use format strings instead of concatenation

def create_INF_source_string(source_num, season, variation, type, layer, source_dir, source_file, lon, lat, num_cells_line, num_lines, cell_x_dim, cell_y_dim):
    contents = "[Source" + source_num + "]\n"
    if season:
        contents += "Season          = " + season + "\n"
    if variation:
        contents += "Variation          = " + variation + "\n"

    contents += "Type          = " + type + "\n"
    contents += "Layer          = " + layer + "\n"
    contents += "SourceDir  = " + source_dir + "\n"
    contents += "SourceFile = " + source_file + "\n"
    contents += "Lon               = " + lon + "\n"
    contents += "Lat               = " + lat + "\n"
    contents += "NumOfCellsPerLine = " + num_cells_line + "       ;Pixel isn't FSX/P3D\n"
    contents += "NumOfLines        = " + num_lines + "       ;Pixel isn't used in FSX/P3D\n"
    contents += "CellXdimensionDeg = """ + cell_x_dim + "\n"
    contents += "CellYdimensionDeg = """ + cell_y_dim + "\n"
    contents += "PixelIsPoint      = 0\n"
    contents += "SamplingMethod    = Point\n"
    contents += "NullValue         = 255,255,255"

    return contents

def should_mask_file(img_mask_abs_path):
    return O4_ESP_Globals.do_build_masks and img_mask_abs_path is not None and os.path.isfile(img_mask_abs_path)

def should_add_blend_mask(should_mask):
    return should_mask and O4_ESP_Globals.build_for_FSX_P3D

def get_total_num_sources(seasons_to_create, build_night, build_water_mask):
    total = 0;
    if seasons_to_create:
        created_summer = False
        for season, should_build in seasons_to_create.items():
            # for fs9, we gotta always build all seasons, so add 1 for every season
            if should_build or O4_ESP_Globals.build_for_FS9:
                total += 1
                if season == "Summer":
                    created_summer = True
        # if at least one season has been built and it is not summer, we always need to create summer
        # to cover the remaining months
        if total > 0 and not created_summer:
            total += 1

    if should_add_blend_mask(build_water_mask):
        # if total == 0, no seasons are being built, so we need to account for the generic, non season bmp source entry
        # TODO: when no seasons being built, just use your new logic which sets the season to summer and sets variation to all months not used...
        if total == 0:
            total += 2
        else:
            total += 1

    if build_night:
        # if total == 0, no seasons are being built, so we need to account for the generic, non season bmp source entry
        # TODO: when no seasons being built, just use your new logic which sets the season to summer and sets variation to all months not used...
        if total == 0:
            total += 2
        else:
            total += 1

    # there will at minimum always be 1 source...
    if total == 0:
        total = 1

    return total

def source_num_to_source_num_string(source_num, total_sources):
    if total_sources == 1:
        return ""

    return str(source_num)

# if user doesn't specify night for fs9, it will just create empty black tile. Better to fill this in with the default
# day texture? or just leave black? I guess leave black for now, it makes it more obvious that maybe they should enable night
def add_remaining_seasons_for_fs9(seasons_to_create, source_num, type, layer, source_dir, source_file, img_mask_folder_abs_path, img_mask_name, lon, lat, num_cells_line, num_lines, cell_x_dim, cell_y_dim, total_sources, should_mask):
    remaining_seasons_inf_str = ""
    source_file_name, ext = os.path.splitext(source_file)
    num_seasons_added = 0
    for season, should_build in seasons_to_create.items():
        if not should_build:
            # just build it with January for month variation, doesn't matter
            remaining_seasons_inf_str += create_INF_source_string(source_num_to_source_num_string(source_num, total_sources), season, "January", type, layer, source_dir, source_file_name + ext, lon, lat, num_cells_line, num_lines, cell_x_dim, cell_y_dim) + "\n\n"
            source_num += 1
            num_seasons_added += 1

    return (remaining_seasons_inf_str, num_seasons_added)

# getting None from this function is a good way of seeing if there are no seasons to build...
def get_seasons_inf_string(seasons_to_create, source_num, type, layer, source_dir, source_file, img_mask_folder_abs_path, img_mask_name, lon, lat, num_cells_line, num_lines, cell_x_dim, cell_y_dim, total_sources, should_mask):
    string = ""
    source_file_name, ext = os.path.splitext(source_file)
    months_used_dict = { "January": False, "February": False, "March": False, "April": False, "May": False, "June": False, "July": False, "August": False, "September": False, "October": False, "November": False, "December": False }

    if seasons_to_create["Spring"]:
        string += create_INF_source_string(source_num_to_source_num_string(source_num, total_sources), "Spring", "March,April,May", type, layer, source_dir, source_file_name + "_spring" + ext, lon, lat, num_cells_line, num_lines, cell_x_dim, cell_y_dim) + "\n\n"
        if should_add_blend_mask(should_mask):
            string += "; pull the blend mask from Source" + str(total_sources) + ", band 0\nChannel_BlendMask = " + str(total_sources) + ".0\n\n"
        source_num += 1
        months_used_dict["March"] = True
        months_used_dict["April"] = True
        months_used_dict["May"] = True
    if seasons_to_create["Fall"]:
        string += create_INF_source_string(source_num_to_source_num_string(source_num, total_sources), "Fall", "September,October", type, layer, source_dir, source_file_name + "_fall" + ext, lon, lat, num_cells_line, num_lines, cell_x_dim, cell_y_dim) + "\n\n"
        if should_add_blend_mask(should_mask):
            string += "; pull the blend mask from Source" + str(total_sources) + ", band 0\nChannel_BlendMask = " + str(total_sources) + ".0\n\n"
        source_num += 1
        months_used_dict["September"] = True
        months_used_dict["October"] = True
    if seasons_to_create["Winter"]:
        string += create_INF_source_string(source_num_to_source_num_string(source_num, total_sources), "Winter", "November", type, layer, source_dir, source_file_name + "_winter" + ext, lon, lat, num_cells_line, num_lines, cell_x_dim, cell_y_dim) + "\n\n"
        if should_add_blend_mask(should_mask):
            string += "; pull the blend mask from Source" + str(total_sources) + ", band 0\nChannel_BlendMask = " + str(total_sources) + ".0\n\n"
        source_num += 1
        months_used_dict["November"] = True
    if seasons_to_create["HardWinter"]:
        string += create_INF_source_string(source_num_to_source_num_string(source_num, total_sources), "HardWinter", "December,January,February", type, layer, source_dir, source_file_name + "_hard_winter" + ext, lon, lat, num_cells_line, num_lines, cell_x_dim, cell_y_dim) + "\n\n"
        if should_add_blend_mask(should_mask):
            string += "; pull the blend mask from Source" + str(total_sources) + ", band 0\nChannel_BlendMask = " + str(total_sources) + ".0\n\n"
        source_num += 1
        months_used_dict["December"] = True
        months_used_dict["January"] = True
        months_used_dict["February"] = True
    # create summer with variation which includes all those months that haven't been included yet. do this if either summer is specified in Ortho4XP.cfg OR
    # if at least one other season has been specified (ie string != "") in order that all months are specified if not all seasons are specified...
    if seasons_to_create["Summer"] or string != "":
        months_str = ""
        for month, has_been_used in months_used_dict.items():
            if not has_been_used:
                months_str += month + ","

        months_str = months_str[:-1]
        string += create_INF_source_string(source_num_to_source_num_string(source_num, total_sources), "Summer", months_str, type, layer, source_dir, source_file_name + ext, lon, lat, num_cells_line, num_lines, cell_x_dim, cell_y_dim) + "\n\n"
        if should_add_blend_mask(should_mask):
            string += "; pull the blend mask from Source" + str(total_sources) + ", band 0\nChannel_BlendMask = " + str(total_sources) + ".0\n\n"
        source_num += 1

    if O4_ESP_Globals.build_for_FS9:
        (remaining_seasons, seasons_added) = add_remaining_seasons_for_fs9(seasons_to_create, source_num, type, layer, source_dir, source_file, img_mask_folder_abs_path, img_mask_name, lon, lat, num_cells_line, num_lines, cell_x_dim, cell_y_dim, total_sources, should_mask)
        string += remaining_seasons
        source_num += seasons_added

    return (string if string != "" else None, source_num - 1)

def clip_to_lod_cell(coordinate, coordinate_type, lod):
    quad_tree_id_type = None

    if coordinate_type == "Latitude":
        quad_tree_id_type = "V"
    elif coordinate_type == "Longitude":
        quad_tree_id_type = "U"

    quad_tree_id_clipped = math.ceil(coord_to_quadtree_id(coordinate, coordinate_type, lod))

    return quadtree_id_to_coord(quad_tree_id_clipped, quad_tree_id_type, lod)

from decimal import *

def coord_to_quadtree_id(coordinate, coord_type, lod):
    QUANTIZE = "1.0000000000000000000000000"
    quantized_coord = Decimal(coordinate).quantize(Decimal(QUANTIZE))
    quantized_lod = Decimal(lod).quantize(Decimal(QUANTIZE))
    quantized_90 = Decimal("90")
    quantized_2 = Decimal("2")
    quantized_120 = Decimal("120")
    quantized_180 = Decimal("180")

    if coord_type == "Latitude":
        return -((quantized_coord - quantized_90) * (quantized_2 ** quantized_lod)) / quantized_90
    if coord_type == "Longitude":
        return ((quantized_coord + quantized_180) * (quantized_2 ** quantized_lod)) / quantized_120

    raise Exception("Unknown coordinate type")

def quadtree_id_to_coord(id, id_type, lod):
    QUANTIZE = "1.00000000000000000000000"
    quantized_id = Decimal(id).quantize(Decimal(QUANTIZE))
    quantized_lod = Decimal(lod).quantize(Decimal(QUANTIZE))
    quantized_90 = Decimal("90")
    quantized_2 = Decimal("2")
    quantized_120 = Decimal("120")
    quantized_180 = Decimal("180")

    if id_type == "V":
        return quantized_90 - quantized_id * (quantized_90 / (quantized_2 ** quantized_lod))
    if id_type == "U":
        return -quantized_180 + quantized_id * (quantized_120 / quantized_2 ** quantized_lod)

    raise Exception("Unknown id type")

def get_clipped_FS9_coords(img_top_left_tile, img_bottom_right_tile, lod):
    north_lat = clip_to_lod_cell(img_top_left_tile[0], "Latitude", lod)
    south_lat = clip_to_lod_cell(img_bottom_right_tile[0], "Latitude", lod)
    west_lon = clip_to_lod_cell(img_top_left_tile[1], "Longitude", lod)
    east_lon = clip_to_lod_cell(img_bottom_right_tile[1], "Longitude", lod)

    return (north_lat, south_lat, west_lon, east_lon)

def get_clipped_FS9_coords_with_offset(img_top_left_tile, img_bottom_right_tile, img_cell_x_dimension_deg, img_cell_y_dimension_deg, lod):
    clipped_coords = get_clipped_FS9_coords(img_top_left_tile, img_bottom_right_tile, 13)
    PIXEL_OFFSET_MULTIPLIER = 0.5

    north_lat = float(clipped_coords[0]) - (PIXEL_OFFSET_MULTIPLIER * img_cell_y_dimension_deg)
    south_lat = float(clipped_coords[1]) + (PIXEL_OFFSET_MULTIPLIER * img_cell_y_dimension_deg)
    west_lon = float(clipped_coords[2]) + (PIXEL_OFFSET_MULTIPLIER * img_cell_x_dimension_deg)
    east_lon = float(clipped_coords[3]) - (PIXEL_OFFSET_MULTIPLIER * img_cell_x_dimension_deg)

    return (north_lat, south_lat, west_lon, east_lon)

def get_FS9_destination_lat_lon_str(img_top_left_tile, img_bottom_right_tile, img_cell_x_dimension_deg, img_cell_y_dimension_deg):
    new_coords = get_clipped_FS9_coords_with_offset(img_top_left_tile, img_bottom_right_tile, img_cell_x_dimension_deg, img_cell_y_dimension_deg, 13)

    north_lat = new_coords[0]
    south_lat = new_coords[1]
    west_lon = new_coords[2]
    east_lon = new_coords[3]

    return_str = "NorthLat             = " + str(north_lat) + "\n"
    return_str += "SouthLat             = " + str(south_lat) + "\n"
    return_str += "WestLon             = " + str(west_lon) + "\n"
    return_str += "EastLon             = " + str(east_lon) + "\n"

    return return_str

def determine_img_nw_se_coords(tile, til_x_left, til_x_right, til_y_top, til_y_bot, img_top_left_tile, img_bottom_right_tile, zoomlevel):
    clamp = lambda value, min_val, max_val: max(min(value, max_val), min_val)

    clamped_img_top_left_coords = [
        clamp(img_top_left_tile[0], tile.lat, tile.lat + 1),
        clamp(img_top_left_tile[1], tile.lon, tile.lon + 1)
    ]
    clamped_img_bottom_right_coords = [
        clamp(img_bottom_right_tile[0], tile.lat, tile.lat + 1),
        clamp(img_bottom_right_tile[1], tile.lon, tile.lon + 1)
    ]

    return (clamped_img_top_left_coords, clamped_img_bottom_right_coords)

def get_mask_paths(file_name):
    img_mask_name = "_".join(file_name.split(".bmp")[0].split("_")[0:2]) + ".tif"
    img_mask_folder_abs_path = os.path.abspath(O4_ESP_Globals.mask_dir)
    img_mask_abs_path = os.path.abspath(os.path.join(img_mask_folder_abs_path, img_mask_name))

    return img_mask_name, img_mask_folder_abs_path, img_mask_abs_path

# TODO: all this night/season mask code is kind of terrible... need to refactor
# TODO: do we really need the use_FS9_type? We can just use the build_for_FS9 global...
def make_ESP_inf_file(tile, file_dir, file_name, til_x_left, til_x_right, til_y_top, til_y_bot, zoomlevel, use_FS9_type=False):
    file_name_no_extension, extension = os.path.splitext(file_name)
    img_top_left_tile = gtile_to_wgs84(til_x_left, til_y_top, zoomlevel)
    img_bottom_right_tile = gtile_to_wgs84(til_x_right, til_y_bot, zoomlevel)
    clamped_img_top_left, clamped_img_bottom_right = determine_img_nw_se_coords(tile, til_x_left, til_x_right,
                                                                          til_y_top, til_y_bot, img_top_left_tile, img_bottom_right_tile,
                                                                          zoomlevel)
    (IMG_X_DIM, IMG_Y_DIM) = O4_Imagery_Utils.get_image_dimensions(file_dir + os.sep + file_name)

    img_cell_x_dimension_deg = (clamped_img_bottom_right[1] - clamped_img_top_left[1]) / IMG_X_DIM
    img_cell_y_dimension_deg = (clamped_img_top_left[0] - clamped_img_bottom_right[0]) / IMG_Y_DIM

    img_mask_name, img_mask_folder_abs_path, img_mask_abs_path = get_mask_paths(file_name)
    if O4_ESP_Globals.build_for_FS9:
        new_coords = get_clipped_FS9_coords(clamped_img_top_left, clamped_img_bottom_right, 13)
        north_lat = new_coords[0]
        south_lat = new_coords[1]
        west_lon = new_coords[2]
        east_lon = new_coords[3]
        img_top_left_tile = (north_lat, west_lon)
        img_bottom_right_tile = (south_lat, east_lon)
        clamped_img_top_left = img_top_left_tile
        clamped_img_bottom_right = img_bottom_right_tile

        img_cell_x_dimension_deg = float((clamped_img_bottom_right[1] - clamped_img_top_left[1]) / IMG_X_DIM)
        img_cell_y_dimension_deg = float((clamped_img_top_left[0] - clamped_img_bottom_right[0]) / IMG_Y_DIM)

    with open(file_dir + os.sep + file_name_no_extension + ".inf", "w") as inf_file:
        # make sure we have the mask tile created by Ortho4XP. even if do_build_masks is True, if tile not created
        # we don't tell resample to mask otherwise it will fail
        should_mask = should_mask_file(img_mask_abs_path)
        seasons_to_create = {
            "Summer": O4_Config_Utils.create_ESP_summer,
            "Spring": O4_Config_Utils.create_ESP_spring,
            "Fall": O4_Config_Utils.create_ESP_fall,
            "Winter": O4_Config_Utils.create_ESP_winter,
            "HardWinter": O4_Config_Utils.create_ESP_hard_winter
        }
        contents = ""
        total_num_sources = get_total_num_sources(seasons_to_create, O4_Config_Utils.create_ESP_night, should_mask)
        if total_num_sources > 1:
            contents = "[Source]\nType = MultiSource\nNumberOfSources = " + str(total_num_sources) + "\n\n"

        current_source_num = 1
        bmp_type = "BMP"
        if use_FS9_type:
            bmp_type = "Custom"
        seasons_string, num_seasons = get_seasons_inf_string(seasons_to_create, current_source_num, bmp_type, "Imagery", os.path.abspath(file_dir), file_name, img_mask_folder_abs_path, img_mask_abs_path,
        str(clamped_img_top_left[1]), str(clamped_img_top_left[0]), str(IMG_X_DIM), str(IMG_Y_DIM), str(img_cell_x_dimension_deg), str(img_cell_y_dimension_deg), total_num_sources, should_mask)
        # if seasons_string is not None, there are seasons to build in Ortho4XP.cfg
        if seasons_string:
            current_source_num += num_seasons
            contents += seasons_string

        if O4_Config_Utils.create_ESP_night:
            source_num_str = source_num_to_source_num_string(current_source_num, total_num_sources)
            ext = ".bmp"
            if O4_ESP_Globals.build_for_FS9:
                ext = ".tga"

            contents += create_INF_source_string(source_num_str, "LightMap", "LightMap", bmp_type, "Imagery", os.path.abspath(file_dir), file_name_no_extension + "_night" + ext, str(clamped_img_top_left[1]),
                    str(clamped_img_top_left[0]), str(IMG_X_DIM), str(IMG_Y_DIM), str(img_cell_x_dimension_deg), str(img_cell_y_dimension_deg)) + "\n\n"
            if should_add_blend_mask(should_mask):
                contents += "; pull the blend mask from Source" + str(total_num_sources) + ", band 0\nChannel_BlendMask = " + str(total_num_sources) + ".0\n\n"
            current_source_num += 1

        # TODO: when no seasons being built, just use your new logic which sets the season to summer and sets variation to all months not used...
        if seasons_string is None:
            source_num_str = source_num_to_source_num_string(current_source_num, total_num_sources)
            contents += create_INF_source_string(source_num_str, None, None, bmp_type, "Imagery", os.path.abspath(file_dir), file_name, str(clamped_img_top_left[1]),
                        str(clamped_img_top_left[0]), str(IMG_X_DIM), str(IMG_Y_DIM), str(img_cell_x_dimension_deg), str(img_cell_y_dimension_deg)) + "\n\n"
            if should_add_blend_mask(should_mask):
                contents += "; pull the blend mask from Source" + str(total_num_sources) + ", band 0\nChannel_BlendMask = " + str(total_num_sources) + ".0\n\n"

            current_source_num += 1

        if should_add_blend_mask(should_mask):
            mask_type = "Custom" if use_FS9_type else "Tiff"
            source_num_str = source_num_to_source_num_string(current_source_num, total_num_sources)
            contents += create_INF_source_string(source_num_str, None, None, bmp_type, "None", img_mask_folder_abs_path, img_mask_name, str(clamped_img_top_left[1]),
                    str(clamped_img_top_left[0]), str(IMG_X_DIM), str(IMG_Y_DIM), str(img_cell_x_dimension_deg), str(img_cell_y_dimension_deg)) + "\n\n"

        contents += "[Destination]\n"
        contents += "DestDir             = " + os.path.abspath(file_dir) + os.sep + "ADDON_SCENERY" + os.sep + "scenery\n"
        contents += "DestBaseFileName     = " + file_name_no_extension + "\n"
        contents += "BuildSeasons        = " + ("1" if (O4_ESP_Globals.build_for_FS9 and seasons_string is not None) else "0") + "\n"
        contents += "UseSourceDimensions  = " + ("0" if (O4_ESP_Globals.build_for_FS9 and seasons_string is not None) else "1") + "\n"
        contents += "CompressionQuality   = 100\n"
        if O4_ESP_Globals.build_for_FS9:
            contents += get_FS9_destination_lat_lon_str(clamped_img_top_left, clamped_img_bottom_right, img_cell_x_dimension_deg, img_cell_y_dimension_deg)

        # Default land class textures will be used if the terrain system cannot find photo-imagery at LOD13 (5 meters per pixel) or greater detail.
        # source: https://docs.microsoft.com/en-us/previous-versions/microsoft-esp/cc707102(v=msdn.10)
        # otherwise, nothing will be added, so the default of LOD = Auto will be used
        LOD_13_DEG_PER_PIX = 4.27484e-05
        if img_cell_x_dimension_deg > LOD_13_DEG_PER_PIX or img_cell_y_dimension_deg > LOD_13_DEG_PER_PIX:
            contents += "LOD = Auto, 13\n"

        inf_file.write(contents)

def spawn_resample_process(filename):
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startupinfo.wShowWindow = 7 # subprocess.SW_SHOWMINNOACTIVE is 7
    resample_exe_loc = O4_Config_Utils.FSX_P3D_resample_loc
    if O4_ESP_Globals.build_for_FS9:
        resample_exe_loc = O4_Config_Utils.FS9_resample_loc

    process = subprocess.Popen([resample_exe_loc, filename], creationflags=subprocess.CREATE_NEW_CONSOLE, startupinfo=startupinfo)
    # wait until done
    process.communicate()

def remove_file_if_exists(filename):
    try:
        os.remove(filename)
    except OSError:
        pass

# this looks ugly. TODO: try to clean
def create_night_and_seasonal_textures(file_name, img_extension, img_mask_abs_path):
    if O4_Config_Utils.create_ESP_night:
        create_night(file_name + img_extension, file_name + "_night" + img_extension, img_mask_abs_path)
    if O4_Config_Utils.create_ESP_spring:
        create_spring(file_name + img_extension, file_name + "_spring" + img_extension, img_mask_abs_path)
    if O4_Config_Utils.create_ESP_fall:
        create_autumn(file_name + img_extension, file_name + "_fall" + img_extension, img_mask_abs_path)
    if O4_Config_Utils.create_ESP_winter:
        create_winter(file_name + img_extension, file_name + "_winter" + img_extension, img_mask_abs_path)
    if O4_Config_Utils.create_ESP_hard_winter:
        create_hard_winter(file_name + img_extension, file_name + "_hard_winter" + img_extension, img_mask_abs_path)

    if O4_ESP_Globals.build_for_FS9 and should_mask_file(img_mask_abs_path):
        # need to make black pixels in the main image (aka image_path) where the mask is black too.
        # bug in FS2004? i dont know, but not only one with this issue:
        # https://www.avsim.com/forums/topic/79426-help-with-fs2004-terrain-sdk-alpha-water-mask/
        FS9_mask_main_image(file_name + img_extension, file_name + img_extension, img_mask_abs_path)

        if O4_Config_Utils.create_ESP_night:
            O4_Imagery_Utils.add_image_as_anothers_alpha_channel(file_name + "_night" + img_extension, img_mask_abs_path, file_name + "_night.tga")
        if O4_Config_Utils.create_ESP_spring:
            O4_Imagery_Utils.add_image_as_anothers_alpha_channel(file_name + "_spring" + img_extension, img_mask_abs_path, file_name + "_spring.tga")
        if O4_Config_Utils.create_ESP_fall:
            O4_Imagery_Utils.add_image_as_anothers_alpha_channel(file_name + "_fall" + img_extension, img_mask_abs_path, file_name + "_fall.tga")
        if O4_Config_Utils.create_ESP_winter:
            O4_Imagery_Utils.add_image_as_anothers_alpha_channel(file_name + "_winter" + img_extension, img_mask_abs_path, file_name + "_winter.tga")
        if O4_Config_Utils.create_ESP_hard_winter:
            O4_Imagery_Utils.add_image_as_anothers_alpha_channel(file_name + "_hard_winter" + img_extension, img_mask_abs_path, file_name + "_hard_winter.tga")

# TODO: cleanup processes when main program quits
def worker(queue):
    # """Process files from the queue."""
    for args in iter(queue.get, None):
        try:
            file_name = args[0]
            inf_abs_path = args[1]
            img_mask_abs_path = args[2]

            img_extension = ".bmp"

            if O4_ESP_Globals.build_for_FS9:
                img_extension = ".tga"
                if should_mask_file(img_mask_abs_path):
                    O4_Imagery_Utils.add_image_as_anothers_alpha_channel(file_name + img_extension, img_mask_abs_path, file_name + img_extension)
                else:
                    # no mask, but fs2004 resample still needs the alpha channel. we just pass in an alpha with all 255 (white)
                    O4_Imagery_Utils.add_image_as_anothers_alpha_channel(file_name + img_extension, img_mask_abs_path, file_name + img_extension, 255)

            # we create the night and seasonal textures at resample time, and delete them right after...
            # why? to not require a ridiculously large amount of storage space...
            create_night_and_seasonal_textures(file_name, img_extension, img_mask_abs_path)

            spawn_resample_process(inf_abs_path)
            # now remove the extra night/season bmps
            # could check if we created night, season, etc but let's be lazy and use remove_file_if_exists
            remove_file_if_exists(file_name + "_night" + img_extension)
            remove_file_if_exists(file_name + "_spring" + img_extension)
            remove_file_if_exists(file_name + "_fall" + img_extension)
            remove_file_if_exists(file_name + "_winter" + img_extension)
            remove_file_if_exists(file_name + "_hard_winter" + img_extension)
        except Exception as e: # catch exceptions to avoid exiting the
                               # thread prematurely
            print('%r failed: %s' % (args, e,))

def spawn_scenproc_process(scenproc_script_file, scenproc_osm_file, texture_folder):
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startupinfo.wShowWindow = 7 # subprocess.SW_SHOWMINNOACTIVE is 7
    process = subprocess.Popen([O4_Config_Utils.ESP_scenproc_loc, scenproc_script_file, "/run", scenproc_osm_file, texture_folder],
                                creationflags=subprocess.CREATE_NEW_CONSOLE, startupinfo=startupinfo)
    # wait until done
    process.communicate()

def run_scenproc_threaded(queue):
    # """Process files from the queue."""
    for args in iter(queue.get, None):
        try:
            scenproc_script_file = args[0]
            scenproc_osm_file = args[1]
            texture_folder = args[2]
            spawn_scenproc_process(scenproc_script_file, scenproc_osm_file, texture_folder)
        except Exception as e: # catch exceptions to avoid exiting the
                               # thread prematurely
            print('%r failed: %s' % (args, e,))


def can_build_for_ESP():
    if O4_ESP_Globals.build_for_FSX_P3D:
        if O4_Config_Utils.FSX_P3D_resample_loc == '':
            print("No FSX/P3D resample.exe is specified in Ortho4XP.cfg, quitting")
            return False
        if not os.path.isfile(O4_Config_Utils.FSX_P3D_resample_loc):
            print("FSX/P3D resample.exe doesn't exist at " + O4_Config_Utils.FSX_P3D_resample_loc + ", quitting")
            return False

    if O4_ESP_Globals.build_for_FS9:
        if O4_Config_Utils.FS9_resample_loc == '':
            print("No FS9 resample.exe is specified in Ortho4XP.cfg, quitting")
            return False
        if not os.path.isfile(O4_Config_Utils.FS9_resample_loc):
            print("FS9 resample.exe doesn't exist at " + O4_Config_Utils.FS9_resample_loc + ", quitting")
            return False

    return True

# wrote own function because couldn't get windows copy to work with wildcard even with shell=True
def move_mips_to_texture_folder(mips_path, texture_path, new_extension):
    files = glob.glob(mips_path)
    for f in files:
        base_name = os.path.basename(f)
        name, ext = os.path.splitext(base_name)
        new_path = texture_path + name + ".bmp"

        try:
            os.rename(f, new_path)
        except Exception:
            os.remove(new_path)
            os.rename(f, new_path)

def build_for_ESP(build_dir, tile):
    if not build_dir:
        print("ESP_build_dir is None inside of resample... something went wrong, so can't run resample")
        return

    if not can_build_for_ESP():
        return
    # run ScenProc if user has specified path to the scenProc.exe and OSM file was successfully downloaded previously
    scenproc_osm_directory = os.path.abspath(os.path.join(FNAMES.osm_dir(tile.lat, tile.lon), "scenproc_osm_data"))
    scenproc_thread = None
    q2 = None

    # fs9 doesn't seem to create these folders. Create them... won't hurt for fsx/p3d either
    addon_scenery_folder = os.path.abspath(os.path.join(build_dir, "ADDON_SCENERY"))
    scenery_folder = os.path.abspath(os.path.join(addon_scenery_folder, "scenery"))
    texture_folder = os.path.abspath(os.path.join(addon_scenery_folder, "Texture"))
    if not os.path.exists(addon_scenery_folder):
        os.mkdir(addon_scenery_folder)
    if not os.path.exists(texture_folder):
        os.mkdir(texture_folder)
    if not os.path.exists(scenery_folder):
        os.mkdir(scenery_folder)

    if os.path.isfile(O4_Config_Utils.ESP_scenproc_loc) and os.path.exists(scenproc_osm_directory):
        scenproc_script_file = os.path.abspath(FNAMES.scenproc_script_file(O4_Config_Utils.ESP_scenproc_script))

        q2 = Queue()
        scenproc_thread = Thread(target=run_scenproc_threaded, args=(q2, ))
        scenproc_thread.daemon = True
        scenproc_thread.start()
        for (dirpath, dir_names, file_names) in os.walk(scenproc_osm_directory):
            print("Running ScenProc... Run the below command on each file in this directory if you want to run scenProc manually:")
            first_scenproc_file = os.path.abspath(os.path.join(scenproc_osm_directory, file_names[0]))
            print(O4_Config_Utils.ESP_scenproc_loc + " " + scenproc_script_file + " /run " + first_scenproc_file + " " + texture_folder)
            for full_file_name in file_names:
                scenproc_osm_file_name = os.path.abspath(os.path.join(scenproc_osm_directory, full_file_name))
                q2.put_nowait([scenproc_script_file, scenproc_osm_file_name, texture_folder])
        
    # call resample on each individual file, to avoid file name too long errors with subprocess
    # https://stackoverflow.com/questions/2381241/what-is-the-subprocess-popen-max-length-of-the-args-parameter
    # passing shell=True to subprocess didn't help with this error when there are a large amount of inf files to process
    # another solution would be to create inf files with multiple sources, but the below is simpler to code...
	# start threads
    print("Starting ESP queue with a max of " + str(O4_Config_Utils.max_resample_processes) + " processes. *Resample windows will open minimized to the task bar. This process will take a while... you will be notified when finished")
    q = Queue()
    threads = [Thread(target=worker, args=(q,)) for _ in range(O4_Config_Utils.max_resample_processes)]
    for t in threads:
        t.daemon = True # threads die if the program dies
        t.start()

    for (dirpath, dir_names, file_names) in os.walk(build_dir):
        for full_file_name in file_names:
            file_name, file_extension = os.path.splitext(os.path.abspath(build_dir + os.sep + full_file_name))
            if file_extension == ".inf":
                inf_abs_path = file_name + file_extension

                # TODO: refactor below code into function as you've repeated it above...
                img_mask_name = "_".join(full_file_name.split(".inf")[0].split("_")[0:2]) + ".tif"
                img_mask_folder_abs_path = os.path.abspath(O4_ESP_Globals.mask_dir)
                img_mask_abs_path = os.path.abspath(os.path.join(img_mask_folder_abs_path, img_mask_name))
                should_mask = should_mask_file(img_mask_abs_path)
                if not should_mask:
                    img_mask_abs_path = None

                # subprocess.call([O4_Config_Utils.FSX_P3D_resample_loc, inf_abs_path])
                q.put_nowait([file_name, inf_abs_path, img_mask_abs_path])
    
    for _ in threads: q.put_nowait(None) # signal no more files
    if scenproc_thread is not None:
        q2.put_nowait(None)

    for t in threads: t.join() # wait for completion

    # cleanup fs9 imagetool files
    if O4_ESP_Globals.build_for_FS9:
        startupinfo = subprocess.STARTUPINFO()
        # possible BUG: can we ever download a tga which starts with a 0?
        tgas = "%s\\0*.tga" % (os.path.abspath(build_dir))
        mips = "%s\\0*.mip" % (os.path.abspath(build_dir))
        process = subprocess.Popen([O4_Config_Utils.FS9_imagetool_loc, "-nogui", "-terrainphoto", tgas],
        creationflags=subprocess.CREATE_NEW_CONSOLE, startupinfo=startupinfo)
        # wait until done
        process.communicate()

        move_mips_to_texture_folder("%s" % (mips), "%s\\ADDON_SCENERY\\Texture\\" % (os.path.abspath(build_dir)), ".bmp")
        process = subprocess.Popen(["del", "%s" % (tgas)], startupinfo=startupinfo, shell=True)
        # wait until done
        process.communicate()

    # now ensure scenproc threads complete
    if scenproc_thread is not None:
        scenproc_thread.join()
