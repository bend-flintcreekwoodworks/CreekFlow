import xml.etree.ElementTree as ET
import pandas as pd
import io

def parse_room_to_parts(des_path: str) -> pd.DataFrame:
    # Read file lines and remove the first line if it equals "13"
    with open(des_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
        if lines and lines[0].strip() == "13":
            lines = lines[1:]
    xml_content = ''.join(lines)
    
    # Parse the XML content
    tree = ET.parse(io.StringIO(xml_content))
    root = tree.getroot()

    # Instead of using root.find('Products'), search for all <Product> tags anywhere.
    products = root.findall('.//Product')
    print("Found", len(products), "Product elements")
    for product in products:
        print("Product attributes:", product.attrib)
    
    parts = []
    # Iterate over each Product element (each cabinet)
    for product in products:
        # Get the cabinet number from the Product element (adjust the attribute name if needed)
        cab_number = product.attrib.get("CabNo", "Unknown")
        
        # Iterate over all CabProdPart elements within this product (recursively)
        for part in product.findall('.//CabProdPart'):
            name = part.attrib.get("Name", "")
            quantity = part.attrib.get("Quan", "1")
            width = part.attrib.get("W", "")
            length = part.attrib.get("L", "")
            ptype = part.attrib.get("Type", "")
            comment = part.attrib.get("Comment", "")

            part_data = {
                'cabinet_number': cab_number,
                'name': name,
                'quantity': int(float(quantity)) if quantity else 1,
                'width': float(width) if width else None,
                'length': float(length) if length else None,
                'type': ptype,
                'comment': comment,
                'scanned': False  # For barcode tracking later
            }
            parts.append(part_data)

    return pd.DataFrame(parts)

