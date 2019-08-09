import os.path
import sys
import xml.etree.ElementTree as ET


def load_pom_file(pom_path):
    pom_info = {'path': pom_path}
    pom_tree = ET.parse(pom_path)
    root = pom_tree.getroot()
    nsmap = {'m': 'http://maven.apache.org/POM/4.0.0'}
   
    pom_info['groupId'] = ''
    pom_info['artifactId'] = ''
    pom_info['version'] = ''
    pom_info['name'] = ''
    pom_info['packaging'] = ''
    pom_info['parent'] = {'groupId': '', 'artifactId': '', 'version': ''}
    
    dependencies_el = root.findall('*/m:dependencies/m:dependency', nsmap)

    
    return pom_info
    
def main():
    root_path = '/cygdrive/c/dev/workspace'

    pom_path = os.path.join(root_path, 'cipo-ec-dependencies', 'pom.xml')
    pom_info = load_pom_file(pom_path)
    print(pom_info)
    
if __name__ == "__main__":
    main()
