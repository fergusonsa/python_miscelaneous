import argparse
import io
import zipfile

def searchFile(jar_path, archive, library_name):
    list1 = [x for x in archive.namelist() if library in x or x.endswith(".jar") or x.endswith(".ear") or x.endswith(".war")]
    
    for ele in list1:
        if library_name in ele:
            print("\nFound library '{0}' inside {1} in file {2}\n".format(library_name, jar_path, ele))
            return True
        else:
            print("checking {0} inside {1}".format(ele, jar_path))
            zfiledata = io.BytesIO(archive.read(ele))
            with zipfile.ZipFile(zfiledata) as zfile2:
                if searchFile(jar_path + "::" + ele, zfile2, library_name):
                    return True
                    
def main(jar_path, library_name):
    with zipfile.ZipFile(jar_path,'r') as archive:
        if not searchFile(jar_path, archive, library_name):
            print("Could not find the library {0} inside {1}.")

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("jar")
    parser.add_argument("library")
    parser.add_argument("-v", dest="verbose", action="store_true")
    
    args = parser.parse_args()
    main(args.jar, args.library)
