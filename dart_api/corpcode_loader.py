import xml.etree.ElementTree as ET

def get_corp_code(company_name, xml_path="CORPCODE.xml"):
    tree = ET.parse(xml_path)
    root = tree.getroot()

    for corp in root.findall("list"):
        if corp.find("corp_name").text == company_name:
            return corp.find("corp_code").text

    return None
