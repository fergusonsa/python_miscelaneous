
import configparser
import datetime
import os
import os.path
import re

def get_messages_used_in_jsp(jsp_path):
    keys = {}
    regex = r"<fmt:message\s+key=\"([^\"]+)\""
    regex2 = r"<fmt:message\s+key='([^']+)'"

    with open(jsp_path) as f:
        contents = f.read()
        matches = re.finditer(regex, contents, re.MULTILINE)
        matches2 = re.finditer(regex2, contents, re.MULTILINE)

    for matchNum, match in enumerate(matches, start=1):
        # print ("Match {matchNum} was found at {start}-{end}: {match} Actual key: '{group}'".format(matchNum = matchNum, start = match.start(), end = match.end(), match = match.group(), group=match.group(1)))
        keys[match.group(1)] = [jsp_path]
    for matchNum, match in enumerate(matches2, start=1):
        # print ("Match {matchNum} was found at {start}-{end}: {match} Actual key: '{group}'".format(matchNum = matchNum, start = match.start(), end = match.end(), match = match.group(), group=match.group(1)))
        keys[match.group(1)] = [jsp_path]

    # print(keys)
    return keys


def find_messages_used_in_jsp(dir_path):
    results = {}
    listing = os.listdir(dir_path)
    for infile in listing:
        path = os.path.join(dir_path, infile)
        if os.path.isfile(path):
            if os.path.splitext(infile)[1] == '.jsp':
                file_results = get_messages_used_in_jsp(path)
                for key in file_results.keys():
                    if key in results:
                        results[key].extend(file_results[key])
                    else:
                        results[key] = file_results[key]
        elif os.path.isdir(path):
            dir_results = find_messages_used_in_jsp(path)
            for key in dir_results.keys():
                if key in results:
                    results[key].extend(dir_results[key])
                else:
                    results[key] = dir_results[key]

    return results

    
def load_messages_from_properties(properties_path):
    separator = "="
    keys = {}

    with open(properties_path,encoding="ISO-8859-1") as f:
        for line in f:
            if separator in line and not line.startswith('#'):
                # Find the name and value by splitting the string
                name, value = line.split(separator, 1)
                # Assign key value pair to dict
                # strip() removes white space from the ends of strings
                keys[name.strip()] = value.strip()

    # print(keys)
    return keys

def search_file(file_path, patterns):
    results = {}
    text = open(file_path).read()
    for pattern in patterns:        
        match = re.search(pattern, text)
        if match:
            results[pattern] = [file_path]
            
    return results

def search_directory(dir_path, patterns):
    results = {}
    listing = os.listdir(dir_path)
    for infile in listing:
        path = os.path.join(dir_path, infile)
        if os.path.isfile(path):
            if os.path.splitext(infile)[1] == '.jsp':
                file_results = search_file(path, patterns)
                for key in file_results.keys():
                    if key in results:
                        results[key].extend(file_results[key])
                    else:
                        results[key] = file_results[key]
        elif os.path.isdir(path):
            dir_results = search_directory(path, patterns)
            for key in dir_results.keys():
                if key in results:
                    results[key].extend(dir_results[key])
                else:
                    results[key] = dir_results[key]

    return results
def get_log_file_path():
    log_file_path = os.path.join('/cygdrive/c/dev/hague/id_filing_workspace', 'check_message_keys_{}.txt'.format(datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')))
    count = 0
    while os.path.isfile(log_file_path) and count < 2000:
        log_file_path = os.path.join('/cygdrive/c/dev/hague/id_filing_workspace', 'check_message_keys_{}.txt'.format(datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')))
        count += 1
    return log_file_path

def print_and_log(message, log_file_h=None):
    if log_file_h:
        print(message + "\n", file=log_file_h)
    print(message)
        
def main2():
    root_path = '/cygdrive/c/dev/hague/id_filing_workspace/cipo-ec-id-filing/CIPO-ec-id-filing-web'
    # root_path = '/cygdrive/c/dev/hague/id_filing_workspace/cipo-ec-id-mailbox/CIPO-ec-id-mailbox-web'
    jsp_root_path = os.path.join(root_path, 'src','main','webapp','WEB-INF', 'views', 'jsp')
    jsp_sub_folders = ['common', 'mailbox', 'eaccess', 'application', 'amendment', 'fields']
    properties_path = os.path.join(root_path, 'src','main','resources','messages.properties')
    properties_fr_path = os.path.join(root_path, 'src','main','resources','messages_fr.properties')

    en_messages = load_messages_from_properties(properties_path)
    en_patterns = en_messages.keys()
    fr_messages = load_messages_from_properties(properties_fr_path)
    fr_patterns = fr_messages.keys()
    s_en_patterns = set(en_patterns)
    s_fr_patterns = set(fr_patterns)
    all_patterns = list(s_en_patterns.union(s_fr_patterns))
    s_all_patterns = set(all_patterns)

    used_keys = find_messages_used_in_jsp(os.path.join(jsp_root_path, "mailbox"))  
    s_required_keys = set(used_keys.keys())
    
    s_missing_en_required_keys = s_required_keys - s_en_patterns
    s_missing_fr_required_keys = s_required_keys - s_fr_patterns
    s_missing_all_required_keys = s_required_keys - s_all_patterns
    
    log_file_path = get_log_file_path()
    with open(log_file_path, 'w') as log_file_h:
        print_and_log('Found {} keys in the file {}.'.format(len(en_patterns), properties_path), log_file_h)
        print_and_log('Found {} keys in the file {}.'.format(len(fr_patterns), properties_fr_path), log_file_h)
        print_and_log('Found {} unique keys in the files {} and {}.'.format(len(s_all_patterns), properties_path, properties_fr_path), log_file_h)

        print_and_log('\nFound {} keys with occurences in jsp files in {}.'.format(len(used_keys), jsp_root_path), log_file_h)

        print_and_log('\nListing of required message keys that are used in jsps and are not present in any message properties files:', log_file_h)
        for key in sorted(s_missing_all_required_keys):
            print_and_log('    {} in {} jsp files'.format(key, len(used_keys[key])), log_file_h)
                
        print_and_log('\nListing of required message keys that are used in jsps and are not present in the English message properties file:', log_file_h)
        for key in sorted(s_missing_en_required_keys):
            print('    {} in {} jsp files'.format(key, len(used_keys[key])))
            print('    {} in {} jsp files'.format(key, len(used_keys[key])), file=log_file_h)
                
        print_and_log('\nListing of required message keys that are used in jsps and are not present in the French message properties file:', log_file_h)
        for key in sorted(s_missing_fr_required_keys):
            print_and_log('    {} in {} jsp files'.format(key, len(used_keys[key])), log_file_h)
        
    print('\n\nLog file: {}'.format(log_file_path))

def main(root_path):
    jsp_root_path = os.path.join(root_path, 'src', 'main', 'webapp', 'WEB-INF', 'views', 'jsp')
    jsp_sub_folders = ['common', 'mailbox', 'eaccess', 'application', 'amendment', 'fields']

    properties_path = os.path.join(root_path, 'src','main','resources','messages.properties')
    properties_fr_path = os.path.join(root_path, 'src','main','resources','messages_fr.properties')
        
    used_keys = find_messages_used_in_jsp(jsp_root_path)  
    s_required_keys = set(used_keys.keys())
    
    en_messages = load_messages_from_properties(properties_path)
    en_patterns = en_messages.keys()
    fr_messages = load_messages_from_properties(properties_fr_path)
    fr_patterns = fr_messages.keys()
    s_en_patterns = set(en_patterns)
    s_fr_patterns = set(fr_patterns)
    all_patterns = list(s_en_patterns.union(s_fr_patterns))
    s_all_patterns = set(all_patterns)

    s_missing_en_required_keys = s_required_keys - s_en_patterns
    s_missing_fr_required_keys = s_required_keys - s_fr_patterns
    s_missing_all_required_keys = s_required_keys - s_all_patterns

    log_file_path = get_log_file_path()        
    with open(log_file_path, 'w') as log_file_h:
        print_and_log('Found {} keys in the file {}.'.format(len(en_patterns), properties_path), log_file_h)
        print_and_log('Found {} keys in the file {}.'.format(len(fr_patterns), properties_fr_path), log_file_h)
        print_and_log('Found {} unique keys in the files {} and {}.'.format(len(s_all_patterns), properties_path, properties_fr_path), log_file_h)
    
        print_and_log('\nFound {} keys with occurences in jsp files in {}.'.format(len(used_keys), jsp_root_path), log_file_h)
        
        print_and_log('\nListing of {} required message keys that are used in jsps and are not present in any message properties files:'.format(len(s_missing_all_required_keys)), log_file_h)
        for key in sorted(s_missing_all_required_keys):
            print_and_log('    {:<45} in {} jsp files: {}'.format(key, len(used_keys[key]), used_keys[key]), log_file_h)
                
        print_and_log('\nListing of {} required message keys that are used in jsps and are not present in the English message properties file:'.format(len(s_missing_en_required_keys)), log_file_h)
        for key in sorted(s_missing_en_required_keys):
            print_and_log('    {:<45} in {} jsp files: {}'.format(key, len(used_keys[key]), used_keys[key]), log_file_h)
                
        print_and_log('\nListing of {} required message keys that are used in jsps and are not present in the French message properties file:'.format(len(s_missing_fr_required_keys)), log_file_h)
        for key in sorted(s_missing_fr_required_keys):
            print_and_log('    {:<45} in {} jsp files: {}'.format(key, len(used_keys[key]), used_keys[key]), log_file_h)

        results = search_directory(jsp_root_path, all_patterns)
        print_and_log('\nFound {} keys with occurences in jsp files in {}.'.format(len(results), jsp_root_path), log_file_h)
        
        for sub_dir in jsp_sub_folders:
            sub_path = os.path.join(jsp_root_path, sub_dir)
            if os.path.isdir(sub_path):
                additional_results = search_directory(sub_path, all_patterns)
                print_and_log('Found {} keys with occurences in jsp files in {}.'.format(len(additional_results), sub_path), log_file_h)
                for key in additional_results.keys():
                    if key in results:
                        results[key].extend(additional_results[key])
                    else:
                        results[key] = additional_results[key]

        used_patterns = sorted(results.keys())
        s_used_patterns = set(used_patterns)
        print_and_log('\n\nChecking message keys in the files: \n    {}\n    {}\n'.format(properties_path, properties_fr_path), log_file_h)  
        print_and_log('Checking key usage in the jsp files in: {}'.format(jsp_root_path), log_file_h)
        
        print_and_log('\nListing of message keys that are used and the files that use them:', log_file_h)
        for key in used_patterns:
            print_and_log('\nPattern "{}":'.format(key), log_file_h)
            for val in sorted(results[key]):
                print_and_log('    {}'.format(val), log_file_h)
                
        print_and_log('\nListing of message keys that are used and the files that use them:', log_file_h)
        for key in used_patterns:
            print_and_log('{},"{}","{}"'.format(key, en_messages.get(key), fr_messages.get(key)), log_file_h)

        print_and_log('\n\n\nListing of message keys that are NOT used:', log_file_h)
        for key in sorted(s_all_patterns - s_used_patterns):
            print_and_log('    {}'.format(key), log_file_h)

        unused_patterns = sorted(s_en_patterns - s_used_patterns)
        print_and_log('\n\n\nListing of {} message keys that are not used in {}:'.format(len(unused_patterns), properties_path), log_file_h)

        for key in unused_patterns:
            print_and_log('    {}'.format(key), log_file_h)
        
        unused_patterns = sorted(s_fr_patterns - s_used_patterns)
        print_and_log('\n\n\nListing of {} message keys that are not used in {}:'.format(len(unused_patterns), properties_fr_path), log_file_h)

        for key in unused_patterns:
            print_and_log('    {}'.format(key), log_file_h)
            
        missing = sorted(s_en_patterns - s_fr_patterns)
        print_and_log('\n\n\nListing of {} message keys that are in the {} and not in {}:'.format(len(missing), properties_path, properties_fr_path), log_file_h)

        for key in missing:
            print_and_log('    {}'.format(key), log_file_h)
               
        missing = sorted(s_fr_patterns - s_en_patterns)
        print_and_log('\n\n\nListing of {} message keys that are in the {} and not in {}:'.format(len(missing), properties_fr_path, properties_path), log_file_h)
        for key in sorted(s_fr_patterns - s_en_patterns):
            print_and_log('    {}'.format(key), log_file_h)
                        
    print('\n\nLog file: {}'.format(log_file_path))
    
if __name__ == "__main__":
    root_path = '/cygdrive/c/dev/hague/id_filing_workspace/cipo-ec-id-filing/CIPO-ec-id-filing-web'
    root_path = '/cygdrive/c/dev/hague/new_workspace/cipo-ec-id-filing/CIPO-ec-id-filing-web'
    # root_path = '/cygdrive/c/dev/hague/id_filing_workspace/cipo-ec-id-eaccess/CIPO-ec-id-eaccess-web'
    # root_path = '/cygdrive/c/dev/hague/id_filing_workspace/cipo-ec-id-mailbox/CIPO-ec-id-mailbox-web'
    main(root_path)
