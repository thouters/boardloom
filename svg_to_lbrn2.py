import xml.etree.ElementTree as ET
from xml.dom import minidom
import os

def parse_svg(svg_file):
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

    return shapes

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
        cut_setting = ET.SubElement(project, 'CutSetting', {'type': 'Cut'})
        ET.SubElement(cut_setting, 'index', {'Value': str(index)})
        ET.SubElement(cut_setting, 'name', {'Value': os.path.basename(filename)})
        ET.SubElement(cut_setting, 'maxPower', {'Value': '20'})
        ET.SubElement(cut_setting, 'maxPower2', {'Value': '20'})
        ET.SubElement(cut_setting, 'speed', {'Value': '100'})
        ET.SubElement(cut_setting, 'priority', {'Value': '0'})

    for index, filename in enumerate(filenames):
        group = ET.SubElement(project, 'Shape', {'Type': 'Group'})
        ET.SubElement(group, 'XForm').text = '1 0 0 1 0 0'
        children = ET.SubElement(group, 'Children')

        #python match statement to execute based on file extension (.svg, .png):
        if filename.endswith('.svg'):
            shapes = parse_svg(filename)
            for shape in shapes:
                if shape['type'] == 'Path':
                    shape_elem = ET.SubElement(children, 'Shape', {'Type': 'Path', 'CutIndex': str(index)})
                    ET.SubElement(shape_elem, 'XForm').text = '1 0 0 1 0 0'
                    ET.SubElement(shape_elem, 'VertList').text = format_vertlist(shape['d'])
                    ET.SubElement(shape_elem, 'PrimList').text = 'LineClosed'
                elif shape['type'] == 'Ellipse':
                    shape_elem = ET.SubElement(children, 'Shape', {'Type': 'Ellipse', 'CutIndex': str(index), 'Rx': str(shape['rx']), 'Ry': str(shape['ry']) })
                    ET.SubElement(shape_elem, 'XForm').text = f"1 0 0 -1 {shape['cx']} -{shape['cy']}"
        elif filename.endswith('.png'):

    # Write to file
    xml_str = minidom.parseString(ET.tostring(project)).toprettyxml(indent="    ")
    with open(output_file, 'w') as f:
        f.write(xml_str)

if __name__ == '__main__':
    svg_files = [
        '/home/thomas/pets/sculpfun/svg2lbrn/pir-24v-F_Mask.svg',
#        '/home/thomas/pets/sculpfun/svg2lbrn/pir-24v-F_Silkscreen.svg',
#        '/home/thomas/pets/sculpfun/svg2lbrn/pir-24v-B_Mask.svg',
        # Add more SVG file paths here if needed
    ]
    output_file = '/home/thomas/pets/sculpfun/svg2lbrn/out.lbrn2'

    create_lbrn2(svg_files, output_file)
    print(f"Converted {len(svg_files)} files to {output_file}")