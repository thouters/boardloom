import xml.etree.ElementTree as ET
from xml.dom import minidom
import io
import os
from PIL import Image
import base64
from typing import List, Tuple
import yaml

origin_x = 0
origin_y = 0
board_width_mm = 51
board_height_mm = 71


img_dpi = 300
def parse_svg(svg_file) -> Tuple[dict,List[dict]]:
    """Parse the SVG file and extract shapes."""
    tree = ET.parse(svg_file)
    root = tree.getroot()
    namespace = {'svg': 'http://www.w3.org/2000/svg'}
    shapes = []

    # Extract paths
    for path in root.findall('.//svg:path', namespace):
        d = path.attrib.get('d', '')
        shapes.append({'type': 'Path', 'd': d})

    # Extract circles
    for circle in root.findall('.//svg:circle', namespace):
        cx = float(circle.attrib.get('cx', '0'))
        cy = float(circle.attrib.get('cy', '0'))
        r = float(circle.attrib.get('r', '0'))
        shapes.append({'type': 'Ellipse', 'cx': cx, 'cy': cy, 'rx': r, 'ry': r})

    # width="29.1846mm" height="23.1902mm"
    # Extract width and height from the SVG root element
    width = float(root.attrib.get('width', '0').replace('mm', ''))
    height = float(root.attrib.get('height', '0').replace('mm', ''))
    info = {
        'Width': width,
        'Height': height,
    }

    return (info,shapes)

def format_vertlist(d):
    """Format the VertList to include prefixes and control points."""
    vertices = d.lstrip("M ").rstrip("Z").strip().split(' ')
    formatted = []
    for vertex in vertices:
        coords = vertex.strip().split(',')
        assert len(coords) == 2, f"Invalid vertex format: {vertex}, {d}"
        if len(coords) == 2:
            x, y = coords
            formatted.append(f"V{x} -{y}c0x1c1x1")
    return ''.join(formatted)

def create_lbrn2(config):
    """Create a LightBurn XML file with multiple layers from the given SVG files."""
    input_files = []
    input_files_prefix = config['project']['input_files_prefix']
    output_file = config['project']['output_name']
    layers = config.get('layers', [])
    # Get the input files from the config
    for layer in layers:
        identifier = layer['identifier']
        if "image_settings" in layer:
            default_extension =".png"
        elif "line_settings" in layer:
            default_extension =".svg"
        else:
            raise ValueError(f"Layer {identifier} does not have a valid type.")
        extension = layer.get('extension', default_extension)
        input_files.append(f"{input_files_prefix}{identifier}{extension}")

    project = ET.Element('LightBurnProject', {
        'AppVersion': '1.7.06',
        'DeviceName': 'GRBL',
        'FormatVersion': '1',
        'MaterialHeight': '0',
        'MirrorX': 'False',
        'MirrorY': 'False'
    })

    # Add CutSettings for each layer
    for index, (layer,filename) in enumerate(zip(layers,input_files)):
        if "line_settings" in layer:
            cut_setting = ET.SubElement(project, 'CutSetting', {'type': 'Cut'})
            speed_mm_sec = layer['line_settings']['speed_mm_sec']
            max_power = layer['line_settings']['max_power']
            min_power = layer['line_settings'].get('min_power', int(max_power)-1)
            ET.SubElement(cut_setting, 'index', {'Value': str(index)})
            ET.SubElement(cut_setting, 'name', {'Value': os.path.basename(filename)})
            ET.SubElement(cut_setting, 'maxPower', {'Value':str(max_power)})
            ET.SubElement(cut_setting, 'maxPower2', {'Value': str(min_power)})
            speed_mm_sec = speed_mm_sec
            speed = speed_mm_sec / 60
            ET.SubElement(cut_setting, 'speed', {'Value': str(speed)})
            ET.SubElement(cut_setting, 'priority', {'Value': '0'})
        elif "image_settings" in layer:
            speed_mm_sec = layer['image_settings']['speed_mm_sec']
            line_interval_mm = layer['image_settings']['line_interval_mm']
            cut_setting = ET.SubElement(project, 'CutSetting_Img', {'type': 'Image'})
            max_power = layer['image_settings']['max_power']
            min_power = layer['image_settings'].get('min_power', int(max_power)-1)
            ET.SubElement(cut_setting, 'index', {'Value': str(index)})
            ET.SubElement(cut_setting, 'name', {'Value': os.path.basename(filename)})
            ET.SubElement(cut_setting, 'maxPower', {'Value':str(max_power)})
            ET.SubElement(cut_setting, 'maxPower2', {'Value': str(min_power)})
            # convert speed from mm/sec to mm/min:
            speed_mm_sec = speed_mm_sec
            speed = speed_mm_sec / 60
            ET.SubElement(cut_setting, 'speed', {'Value': str(speed)})
            ET.SubElement(cut_setting, 'bidir', {'Value': '0'})
            ET.SubElement(cut_setting, 'interval', {'Value': str(line_interval_mm)})
            ET.SubElement(cut_setting, 'priority', {'Value': '0'})
            ET.SubElement(cut_setting, 'tabCount', {'Value': '1'})
            ET.SubElement(cut_setting, 'tabCountMax', {'Value': '1'})
            ET.SubElement(cut_setting, 'ditherMode', {'Value': 'threshold'})
            ET.SubElement(cut_setting, 'dpi', {'Value': str(img_dpi)})

    for index, (layer,filename) in enumerate(zip(layers,input_files)):
        #python match statement to execute based on file extension (.svg, .png):
        if "line_settings" in layer:
            info, shapes = parse_svg(filename)
            width_mm = info['Width']
            height_mm = info['Height']
            mirror_y = layer['line_settings'].get('mirror_y',False)
            if mirror_y:
                x = origin_x + board_width_mm/2 + width_mm/2
            else:
                x = origin_x + board_width_mm/2 - width_mm/2
            y = origin_y + height_mm/2 + board_height_mm/2
            group = ET.SubElement(project, 'Shape', {'Type': 'Group'})
            mirror_y_mark = "-" if mirror_y else ""
            ET.SubElement(group, 'XForm').text = f'{mirror_y_mark}1 0 0 1 {x} {y}'
            children = ET.SubElement(group, 'Children')


            for shape in shapes:
                if shape['type'] == 'Path':
                    shape_elem = ET.SubElement(children, 'Shape', {'Type': 'Path', 'CutIndex': str(index)})
                    ET.SubElement(shape_elem, 'XForm').text = f'1 0 0 1 0 0'
                    ET.SubElement(shape_elem, 'VertList').text = format_vertlist(shape['d'])
                    ET.SubElement(shape_elem, 'PrimList').text = 'LineClosed'
                elif shape['type'] == 'Ellipse':
                    shape_elem = ET.SubElement(children, 'Shape', {'Type': 'Ellipse', 'CutIndex': str(index), 'Rx': str(shape['rx']), 'Ry': str(shape['ry']) })
                    ET.SubElement(shape_elem, 'XForm').text = f"1 0 0 -1 {shape['cx']} -{shape['cy']}"
        elif "image_settings" in layer:
            x = origin_x
            y = origin_y
            group = ET.SubElement(project, 'Shape', {'Type': 'Group'})
            ET.SubElement(group, 'XForm').text = f'1 0 0 1 {x} {y}'
            children = ET.SubElement(group, 'Children')

            # Open the image file
            with Image.open(filename) as img:
                width, height = img.size
                # Get the DPI (dots per inch) of the image
                img_dpi_read = img.info.get('dpi', (img_dpi, img_dpi))[0]
                if layer['image_settings']['mirror_y']:
                    img = img.transpose(Image.FLIP_TOP_BOTTOM)

                # Save the mirrored image to a BytesIO buffer
                buffer = io.BytesIO()
                img.save(buffer, format="PNG")

                # Encode the buffer's content to a base64 string
                base64_string = base64.b64encode(buffer.getvalue()).decode('utf-8')


            data = {'Type': 'Bitmap', 'CutIndex': str(index)}
            #add the width of the image to data['W']:
            def to_mm(value, dpi):
                return value * 25.4 / dpi
            height_mm = to_mm(height, img_dpi_read)
            width_mm = to_mm(width, img_dpi_read)
            data['W'] = str(width_mm)
            data['H'] = str(height_mm)
            x = origin_x + width_mm/2
            y = origin_y + height_mm/2
            data['Data'] = base64_string
            shape_elem = ET.SubElement(children, 'Shape', data)
            ET.SubElement(shape_elem, 'XForm').text = f'1 0 0 1 {str(x)} {str(y)}'

    # Write to file
    xml_str = minidom.parseString(ET.tostring(project)).toprettyxml(indent="    ")
    with open(output_file, 'w') as f:
        f.write(xml_str)
    print(f"Converted {len(input_files)} files to {output_file}")

if __name__ == '__main__':
    import sys

    if len(sys.argv) < 2:
        print("Usage: python svg_to_lbrn2.py <yaml_file>")
        sys.exit(1)

    yaml_file = sys.argv[1]

    # Read the YAML file
    with open(yaml_file, 'r') as f:
        config = yaml.safe_load(f)

    create_lbrn2(config)
