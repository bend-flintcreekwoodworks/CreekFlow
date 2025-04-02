import xml.etree.ElementTree as ET
import pandas as pd
import io

def parse_room_to_df(des_path: str) -> pd.DataFrame:
    with open(des_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
        if lines[0].strip() == "13":
            lines = lines[1:]

    xml_content = ''.join(lines)
    tree = ET.parse(io.StringIO(xml_content))
    root = tree.getroot()

    numbered = []
    unnumbered = []

    for product in root.findall('.//Product'):
        cab_no = product.attrib.get('CabNo')
        name = product.attrib.get('ProdName')
        unique_id = product.attrib.get('UniqueID')
        if not cab_no:
            continue

        if product.attrib.get('Numbered') == 'False':
            unnumbered.append({
                'Cabinet Number': f"N{cab_no}",
                'SortKey': int(cab_no),
                'Product Name': name,
                'UniqueID': unique_id
            })
        else:
            numbered.append({
                'Cabinet Number': cab_no,
                'SortKey': int(cab_no),
                'Product Name': name,
                'UniqueID': unique_id
            })

    numbered.sort(key=lambda x: x['SortKey'])
    unnumbered.sort(key=lambda x: x['SortKey'])

    for row in numbered + unnumbered:
        row.pop('SortKey')

    return pd.DataFrame(numbered + unnumbered)
