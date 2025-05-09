import xml.etree.ElementTree as ET
from xml.dom import minidom
import io
import os
from PIL import Image
import base64
from typing import List, Tuple  

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

def create_lbrn2(filenames, output_file):
    """Create a LightBurn XML file with multiple layers from the given SVG files."""
    project = ET.Element('LightBurnProject', {
        'AppVersion': '1.7.06',
        'DeviceName': 'GRBL',
        'FormatVersion': '1',
        'MaterialHeight': '0',
        'MirrorX': 'False',
        'MirrorY': 'False'
    })

    # Add CutSettings for each layer
    for index, filename in enumerate(filenames):
        if filename.endswith('.svg'):
            cut_setting = ET.SubElement(project, 'CutSetting', {'type': 'Cut'})
            ET.SubElement(cut_setting, 'index', {'Value': str(index)})
            ET.SubElement(cut_setting, 'name', {'Value': os.path.basename(filename)})
            ET.SubElement(cut_setting, 'maxPower', {'Value': '20'})
            ET.SubElement(cut_setting, 'maxPower2', {'Value': '20'})
            ET.SubElement(cut_setting, 'speed', {'Value': '100'})
            ET.SubElement(cut_setting, 'priority', {'Value': '0'})
        elif filename.endswith('.png'):
            cut_setting_img = ET.SubElement(project, 'CutSetting_Img', {'type': 'Image'})
            ET.SubElement(cut_setting_img, 'index', {'Value': str(index)})
            ET.SubElement(cut_setting_img, 'name', {'Value': os.path.basename(filename)})
            ET.SubElement(cut_setting_img, 'maxPower', {'Value': '33'})
            ET.SubElement(cut_setting_img, 'maxPower2', {'Value': '20'})
            # convert speed from mm/sec to mm/min:
            speed_mm_sec = 5
            speed = speed_mm_sec / 60
            ET.SubElement(cut_setting_img, 'speed', {'Value': str(speed)})
            ET.SubElement(cut_setting_img, 'bidir', {'Value': '0'})
            line_interval_mm = "0.0847"
            ET.SubElement(cut_setting_img, 'interval', {'Value': line_interval_mm})
            ET.SubElement(cut_setting_img, 'priority', {'Value': '0'})
            ET.SubElement(cut_setting_img, 'tabCount', {'Value': '1'})
            ET.SubElement(cut_setting_img, 'tabCountMax', {'Value': '1'})
            ET.SubElement(cut_setting_img, 'ditherMode', {'Value': 'threshold'})
            ET.SubElement(cut_setting_img, 'dpi', {'Value': str(img_dpi)})

    for index, filename in enumerate(filenames):
        #python match statement to execute based on file extension (.svg, .png):
        if filename.endswith('.svg'):
            info, shapes = parse_svg(filename)
            width_mm = info['Width']
            height_mm = info['Height']
            x = origin_x + board_width_mm/2 - width_mm/2
            y = origin_y + height_mm/2 + board_height_mm/2
            group = ET.SubElement(project, 'Shape', {'Type': 'Group'})
            ET.SubElement(group, 'XForm').text = f'1 0 0 1 {x} {y}'
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
        elif filename.endswith('.png'):
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
                mirrored_img = img.transpose(Image.FLIP_TOP_BOTTOM)
                
                # Save the mirrored image to a BytesIO buffer
                buffer = io.BytesIO()
                mirrored_img.save(buffer, format="PNG")
                
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

if __name__ == '__main__':
    svg_files = [
        '/home/thomas/pets/sculpfun/svg2lbrn/pir-24v-F_Mask.svg',
#        '/home/thomas/pets/sculpfun/svg2lbrn/pir-24v-F_Silkscreen.svg',
#        '/home/thomas/pets/sculpfun/svg2lbrn/pir-24v-B_Mask.svg',
        '/home/thomas/pets/sculpfun/svg2lbrn/pir-24v-F_Cu.png',
        # Add more SVG file paths here if needed
    ]
    output_file = '/home/thomas/pets/sculpfun/svg2lbrn/out.lbrn2'

    create_lbrn2(svg_files, output_file)
    print(f"Converted {len(svg_files)} files to {output_file}")