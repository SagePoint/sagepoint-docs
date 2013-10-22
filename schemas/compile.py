
from collections import Iterable, Mapping
import glob
import json
import os
import sys

# !!! Add logging! Debug!? Trace?!
# !!! Command-line args?

template_extension = 'json'
template_dir = 'templates'
combined_output_dir = 'output/combined'
absolute_path_output_dir = 'output/absolute'

# Some stats? Why not!
stats = {
    'file': {
        'reads':0,
        'writes': 0
    },
    'cache': {
        'hits': 0,
        'misses': 0
    },
    'templates': {}
}

# Output data with absolute pathes?
output_absolute = False

# Cache the read/parsed templates
template_cache = {}

def read_template(template_name):
    """Read and parse the contents of template_name. This will call :func:`replace_references` and additionally cache parsed template data.

    :param template_name: The name of the template file (including .json)
    :type template_name: str
    :return: The template data (as a dict)
    """

    if not template_name in stats['templates']:
        stats['templates'][template_name] = {'cache': {'hits':0,'misses':0}, 'recursive_details': {'num_calls': 0, 'max_depth': 0}}

    # Check the cache first
    if template_name in template_cache:
        stats['cache']['hits'] += 1
        stats['templates'][template_name]['cache']['hits'] += 1
        return template_cache[template_name]

    try:
        # Not int he cache, look for the file
        with open('/'.join([template_dir,template_name])) as template_file:
            template_data = json.load(template_file)

        # Replace references
        replace_references(template_data, template_name)

        stats['file']['reads'] += 1
        stats['cache']['misses'] += 1
        stats['templates'][template_name]['cache']['misses'] += 1

        # Cache it
        template_cache[template_name] = template_data
    except (ValueError) as e:
        print "Error processing {0}: {1}".format(template_name, unicode(e))
        sys.exit(1)

    return template_data

def write_output(template_name, template_data):
    """Write the given template data (dict) to the given file in the correct
    output directory (based on output_absolute).

    :param template_name: The name of the template (including .json)
    :type template_name: str
    :param template_data: The template data
    :type template_data: dict
    """
    target_file_name = '/'.join([combined_output_dir,template_name])
    if output_absolute:
        target_file_name = '/'.join([absolute_path_output_dir,template_name])

    with open(target_file_name, 'w') as output_file:
        json.dump(template_data, output_file, sort_keys=True, indent=4, separators=(',', ': '))

    stats['file']['writes'] += 1

def replace_references(d, template_name, depth=0):
    """Recusively run through the dictionary and replace and "$ref" entries with the associated template contents. This will also
    support "extends" and "allOf" references for inheritance.

    This function is recusive and may hit the recusion limit. If it does, try this:
        import sys
        sys.setrecursionlimit(10000) # Or some equally high value

    That said, more than 1000 recursive calls is going to get... nasty: http://neopythonic.blogspot.com/2009/04/tail-recursion-elimination.html

    :param d: The dictionary to process
    :type d: dict
    :param template_name: The name of the template, used for stats.
    :type template_name: str
    :param depth: The current recusive depth. Defaults to 0 and is used for stats.
    :type depth: int
    """

    # Some stats work
    if depth > stats['templates'][template_name]['recursive_details']['max_depth']:
        stats['templates'][template_name]['recursive_details']['max_depth'] = depth

    # Handle the base reference grabbing and updating
    def __update_referenced_data(d, ref, ref_dict, clear_current_data=False):
        if output_absolute:
            ref_dict['$ref'] = ''.join(['file://',full_absolute_path_output_dir,'/',ref])
        else:
            referenced_data = read_template(ref)
            if not referenced_data:
                raise RuntimeError("Could not find reference {0}".format(ref))
            if clear_current_data:
                for k in d.keys():
                    del d[k]
            d.update(referenced_data)

    # If we are outputting absolute data, update the id (if there is one)
    if output_absolute and depth == 0 and 'id' in d:
        d['id'] = ''.join(['file://',full_absolute_path_output_dir,'/',template_name])


    # Check for Draft 3 extension. In this case we pull in the refrenced data and update
    # the current dict. The NEW way to do this in draft 4 will also work, as the
    # check below will replace the ref in allOf as expected. Fun!
    if 'extends' in d and '$ref' in d['extends']:
        if not 'properties' in d:
            d['properties'] = {}
        __update_referenced_data(d['properties'], d['extends']['$ref'], d['extends'], False)
    # Check for references
    elif '$ref' in d:
        __update_referenced_data(d, d['$ref'], d, True)
    else:
        # Recur further
        for k,v in d.iteritems():
            if isinstance(v, Iterable):
                for piece in v:
                    if isinstance(piece, Mapping):
                        stats['templates'][template_name]['recursive_details']['num_calls'] += 1
                        replace_references(piece, template_name, depth+1)
            if isinstance(v, Mapping):
                stats['templates'][template_name]['recursive_details']['num_calls'] += 1
                replace_references(v, template_name, depth+1)


if __name__ == "__main__":
    # Yup. cwd. That's about it.
    cwd = os.getcwd()
    full_absolute_path_output_dir = ''.join([cwd,'/',absolute_path_output_dir])

    # Create the output directories
    if not os.path.exists(combined_output_dir):
        os.makedirs(combined_output_dir)
    if not os.path.exists(absolute_path_output_dir):
        os.makedirs(absolute_path_output_dir)

    # Pass one, insert data
    for file_name in glob.glob(template_dir + '/*.' + template_extension):
        # Just grab the basename
        file_name = os.path.basename(file_name)
        # Do the real work
        template_data = read_template(file_name)
        write_output(file_name, template_data)

    # Pass two, absolute paths
    template_cache = {}
    output_absolute = True
    for file_name in glob.glob(template_dir + '/*.' + template_extension):
        # Just grab the basename
        file_name = os.path.basename(file_name)
        # Do the real work
        template_data = read_template(file_name)
        write_output(file_name, template_data)

    print json.dumps(stats,sort_keys=True, indent=4, separators=(',', ': '))
