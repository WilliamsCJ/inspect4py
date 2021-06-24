"""
Code Inspector
This script parses a file or files within directory
(and its subdirectories) to extract all the relevant information,
such as documentation, classes (and their methods), functions, etc.
To extract information from docstrings, we have started with the codes
documented.
This tool accepts (for now) only python code (.py)
This script requires `ast`, `cdmcfparser` and `docsting_parse`
be installed within the Python environment you are running 
this script in.
"""

import json
import tokenize

import click
from cdmcfparser import getControlFlowFromFile
from docstring_parser import parse as doc_parse

from staticfg import builder
from utils import *


class CodeInspection:
    def __init__(self, path, out_control_flow_path, out_json_path, flag_png):
        """ init method initializes the Code_Inspection object
        :param self self: represent the instance of the class
        :param str path: the file to inspect
        :param str out_control_flow_path: the output directory to store the control flow information
        :param str out_json_path: the output directory to store the json file with features extracted from the ast tree.
        :param int flag_png: flag to indicate to generate or not control flow figures
        """

        self.path = path
        self.flag_png = flag_png
        self.out_json_path = out_json_path
        self.out_control_flow_path = out_control_flow_path
        self.tree = self.parser_file()
        self.fileInfo = self.inspect_file()
        format = "png"
        self.controlFlowInfo = self.inspect_controlflow(format)
        self.depInfo = self.inspect_dependencies()
        self.classesInfo = self.inspect_classes()
        self.funcsInfo = self.inspect_functions()
        self.bodyInfo = self.inspect_body()
        self.fileJson = self.file_json()

    def parser_file(self):
        """ parse_file method parsers a file as an AST tree
        :param self self: represent the instance of the class
        :return ast.tree: the file as an ast tree
        """

        with tokenize.open(self.path) as f:
            return ast.parse(f.read(), filename=self.path)

    def inspect_file(self):
        """ inspec_file method extracts the features at file level.
        Those features are path, fileNameBase, extension, docstring.
	    The method support several levels of docstrings extraction,
        such as file's long, short a full descrition.
        :param self self: represent the instance of the class
        :return dictionary a dictionary with the file information extracted
        """
        file_info = {}
        file_info["path"] = os.path.abspath(self.path)
        file_name = os.path.basename(self.path).split(".")
        file_info["fileNameBase"] = file_name[0]
        file_info["extension"] = file_name[1]
        ds_m = ast.get_docstring(self.tree)
        docstring = doc_parse(ds_m)
        file_info["doc"] = {}
        file_info["doc"]["long_description"] = docstring.long_description if docstring.long_description else {}
        file_info["doc"]["short_description"] = docstring.short_description if docstring.short_description else {}
        file_info["doc"]["full"] = ds_m if ds_m else {}
        # fileInfo["doc"]["meta"]=docstring.meta if docstring.meta else {}
        return file_info

    def inspect_controlflow(self, format):
        """inspect_controlFlow uses two methods for 
        extracting the controlflow of a file. One as a
        text and another as a figure (PNG/PDF/DOT).   
        
        :param self self: represent the instance of the class
        :param str format: represent the format to save the figure
        :return dictionary: a dictionary with the all information extracted (at file level)
        """
        control_info = {}
        cfg = getControlFlowFromFile(self.path)
        cfg_txt = self._formatFlow(str(cfg))
        cfg_txt_file = self.out_control_flow_path + "/" + self.fileInfo["fileNameBase"] + ".txt"

        with open(cfg_txt_file, 'w') as outfile:
            outfile.write(cfg_txt)
        control_info["cfg"] = cfg_txt_file

        if self.flag_png:
            cfg_visual = builder.CFGBuilder().build_from_file(self.fileInfo["fileNameBase"], self.path)
            cfg_path = self.out_control_flow_path + "/" + self.fileInfo["fileNameBase"]
            cfg_visual.build_visual(cfg_path, format=format, calls=False, show=False)
            control_info["png"] = cfg_path + "." + format
            # delete the second file generated by the cfg_visual (not needed!)
            os.remove(cfg_path)
        else:
            control_info["png"] = "None"
        return control_info

    def inspect_functions(self):
        """ inspect_functions detects all the functions in a AST tree, and calls
        to _f_definitions method to extracts all the features at function level.
        :param self self: represent the instance of the class
        :return dictionary: a dictionary with the all functions information extracted
        """

        functions_definitions = [node for node in self.tree.body if isinstance(node, ast.FunctionDef)]
        funct_def_info = self._f_definitions(functions_definitions)

        # improving the list of calls
        funct_def_info = self._fill_call_name(funct_def_info, self.classesInfo)
        return funct_def_info

    def inspect_classes(self):
        """ inspect_classes detects all the classes and their methods,
         and extracts their features. It also calls to _f_definitions method
        to extract features at method level.
        The features extracted are name, docstring (this information is further analysed
        and classified into several categories), extends, start
        and end of the line and methods.
        :param self self: represent the instance of the class
        :return dictionary: a dictionary with the all classes information extracted
        """

        classes_definitions = [node for node in self.tree.body if isinstance(node, ast.ClassDef)]
        classesInfo = {}
        for c in classes_definitions:
            classesInfo[c.name] = {}
            ds_c = ast.get_docstring(c)
            docstring = doc_parse(ds_c)
            classesInfo[c.name]["doc"] = {}
            classesInfo[c.name]["doc"][
                "long_description"] = docstring.long_description if docstring.long_description else {}
            classesInfo[c.name]["doc"][
                "short_description"] = docstring.short_description if docstring.short_description else {}
            classesInfo[c.name]["doc"]["full"] = ds_c if ds_c else {}
            # classesInfo[c.name]["doc"]["meta"]=docstring.meta if docstring.meta else {}
            try:
                classesInfo[c.name]["extend"] = [b.id for b in c.bases]
            except:
                try:
                    extend = []
                    for b in c.bases:
                        if isinstance(b, ast.Call) and hasattr(b, 'value'):
                            extend.append(b.value.func.id)

                        # capturing extension type: module.import 
                        elif b.value.id and b.attr:
                            extend.append(b.value.id + "." + b.attr)
                        elif b.value.id:
                            extend.append(b.value.id)
                        else:
                            extend.append("")
                    classesInfo[c.name]["extend"] = extend
                    # classesInfo[c.name]["extend"] = [
                    #    b.value.func.id if isinstance(b, ast.Call) and hasattr(b, 'value') else b.value.id if hasattr(b,
                    #                                                                                                  'value') else ""
                    #    for b in c.bases]                                                                                                  #'value') else ""
                except:
                    classesInfo[c.name]["extend"] = []

            classesInfo[c.name]["min_max_lineno"] = self._compute_interval(c)
            methods_definitions = [node for node in c.body if isinstance(node, ast.FunctionDef)]
            classesInfo[c.name]["methods"] = self._f_definitions(methods_definitions)

        # improving the list of calls
        for c in classesInfo:
            classesInfo[c]["methods"] = self._fill_call_name(classesInfo[c]["methods"], classesInfo, c,
                                                             classesInfo[c]["extend"])
        return classesInfo

    def inspect_body(self):
        body_nodes = []
        body_info = {"body": {}}
        for node in self.tree.body:
            if not isinstance(node, ast.ClassDef) and not isinstance(node, ast.FunctionDef) and not isinstance(node,
                                                                                                               ast.Import) and not isinstance(
                    node, ast.ImportFrom):
                body_nodes.append(node)

        body_assigns = [node for node in body_nodes if isinstance(node, ast.Assign)]
        body_expr = [node for node in body_nodes if isinstance(node, ast.Expr)]
        body_store_vars = {}
        body_calls = []
        for b_as in body_assigns:
            if isinstance(b_as.value, ast.Call):
                body_name = self._get_func_name(b_as.value.func)
                body_calls.append(body_name)
                for target in b_as.targets:
                    target_name = self._get_func_name(target)
                    body_store_vars[target_name] = body_name

        for b_ex in body_expr:
            if isinstance(b_ex.value, ast.Call):
                body_name = self._get_func_name(b_ex.value.func)
                body_calls.append(body_name)

        body_info["body"]["calls"] = body_calls
        body_info["body"]["store_vars_calls"] = body_store_vars
        body_info = self._fill_call_name(body_info, self.classesInfo, body=1)
        return body_info

    def inspect_dependencies(self):
        """ inspect_dependencies method extracts the features at dependencies level.
        Those features are module , name, and alias.
        :param self self: represent the instance of the class
        :return dictionary: a dictionary with the all dependencies information extracted
        """

        dep_info = []
        for node in ast.iter_child_nodes(self.tree):
            if isinstance(node, ast.Import):
                module = []
            elif isinstance(node, ast.ImportFrom):
                try:
                    module = node.module
                    # module = node.module.split('.')
                except:
                    module = ''
            else:
                continue
            for n in node.names:
                if "*" in n.name:
                    functions, type = list_functions_from_module(module, self.path)
                    for f in functions:
                        current_dep = {"from_module": module,
                                       "import": f,
                                       "alias": n.asname,
                                       "type": type}
                        dep_info.append(current_dep)
                else:
                    import_name = n.name.split('.')[0]
                    type = type_module(module, import_name, self.path)
                    current_dep = {"from_module": module,
                                   "import": import_name,
                                   "alias": n.asname,
                                   "type": type}
                dep_info.append(current_dep)

        return dep_info

    def _ast_if_main(self):
        """
        Method for getting if the file has a if __name__ == "__main__"
        and if it calls a method (e.g. main, version) or not.
        :param self self: represent the instance of the class
        :return main_info : dictionary with a flag stored in "main_flag" (1 if the if __name__ == main is found, 0 otherwise) 
         and then "main_function" with the name of the function that is called.
        """

        if_main_definitions = [node for node in self.tree.body if isinstance(node, ast.If)]
        if_main_flag = 0
        if_main_func = ""
        main_info = {}

        for node in if_main_definitions:
            try:
                if node.test.comparators[0].s == "__main__":
                    if_main_flag = 1

                funcs_calls = [i.value.func for i in node.body if isinstance(i.value, ast.Call)]
                func_name_id = [self._get_func_name(func) for func in funcs_calls]

                # Note: Assigning just the first name in the list as the main function.
                if func_name_id:
                    if_main_func = self.fileInfo["fileNameBase"] + "." + func_name_id[0]
                    break
            except:
                pass

        main_info["main_flag"] = if_main_flag
        main_info["main_function"] = if_main_func
        if if_main_flag:
            # classifying the type of a main: "test" or "script"
            if "unittest" in if_main_func or "test" in self.fileInfo["fileNameBase"]:
                main_info["type"] = "test"
            else:
                main_info["type"] = "script"
        return main_info

    def file_json(self):
        """file_json method aggregates all the features previously
        extracted from a given file such as, functions, classes 
        and dependencies levels into the same dictionary.
        
        It also writes this new dictionary to a json file.
        :param self self: represent the instance of the class
        :return dictionary: a dictionary with the all information extracted (at file level)
        """

        file_dict = {}
        file_dict["file"] = self.fileInfo
        file_dict["dependencies"] = self.depInfo
        file_dict["classes"] = self.classesInfo
        file_dict["functions"] = self.funcsInfo
        file_dict["body"] = self.bodyInfo["body"]
        file_dict["controlflow"] = self.controlFlowInfo
        file_dict["main_info"] = self._ast_if_main()

        json_file = self.out_json_path + "/" + self.fileInfo["fileNameBase"] + ".json"
        with open(json_file, 'w') as outfile:
            json.dump(prune_json(file_dict), outfile)
        return [file_dict, json_file]

    def _f_definitions(self, functions_definitions):
        """_f_definitions extracts the name, args, doscstring 
        returns, raises of a list of functions or a methods.
        Furthermore, it also extracts automatically several values
        from a docstring, such as long and short description, arguments' 
        name, description, type, default values and if it they are optional
        or not. 
        :param self self: represent the instance of the class
        :param list functions_definitions: represent a list with all functions or methods nodes
        :return dictionary: a dictionary with the all the information at function/method level
        """

        funcs_info = {}
        for f in functions_definitions:
            funcs_info[f.name] = {}
            ds_f = ast.get_docstring(f)
            docstring = doc_parse(ds_f)
            funcs_info[f.name]["doc"] = {}
            funcs_info[f.name]["doc"][
                "long_description"] = docstring.long_description if docstring.long_description else {}
            funcs_info[f.name]["doc"][
                "short_description"] = docstring.short_description if docstring.short_description else {}
            funcs_info[f.name]["doc"]["args"] = {}
            for i in docstring.params:
                funcs_info[f.name]["doc"]["args"][i.arg_name] = {}
                funcs_info[f.name]["doc"]["args"][i.arg_name]["description"] = i.description
                funcs_info[f.name]["doc"]["args"][i.arg_name]["type_name"] = i.type_name
                funcs_info[f.name]["doc"]["args"][i.arg_name]["is_optional"] = i.is_optional
                funcs_info[f.name]["doc"]["args"][i.arg_name]["default"] = i.default
            if docstring.returns:
                r = docstring.returns
                funcs_info[f.name]["doc"]["returns"] = {}
                funcs_info[f.name]["doc"]["returns"]["description"] = r.description
                funcs_info[f.name]["doc"]["returns"]["type_name"] = r.type_name
                funcs_info[f.name]["doc"]["returns"]["is_generator"] = r.is_generator
                funcs_info[f.name]["doc"]["returns"]["return_name"] = r.return_name
            funcs_info[f.name]["doc"]["raises"] = {}
            for num, i in enumerate(docstring.raises):
                funcs_info[f.name]["doc"]["raises"][num] = {}
                funcs_info[f.name]["doc"]["raises"][num]["description"] = i.description
                funcs_info[f.name]["doc"]["raises"][num]["type_name"] = i.type_name

            funcs_info[f.name]["args"] = [a.arg for a in f.args.args]
            rs = [node for node in ast.walk(f) if isinstance(node, (ast.Return,))]
            funcs_info[f.name]["returns"] = [self._get_ids(r.value) for r in rs]
            funcs_info[f.name]["min_max_lineno"] = self._compute_interval(f)
            funcs_calls = [node.func for node in ast.walk(f) if isinstance(node, ast.Call)]
            func_name_id = [self._get_func_name(func) for func in funcs_calls]
            # If we want to store all the calls, included the repeat ones, comment the next
            # line
            func_name_id = list(dict.fromkeys(func_name_id))
            func_name_id = [f_x for f_x in func_name_id if f_x is not None]
            funcs_info[f.name]["calls"] = func_name_id
            funcs_assigns = [node for node in ast.walk(f) if isinstance(node, ast.Assign)]
            funcs_store_vars = {}
            for f_as in funcs_assigns:
                if isinstance(f_as.value, ast.Name) and f_as.value.id == "self":
                    for target in f_as.targets:
                        funcs_store_vars[target.id] = f_as.value.id
                elif isinstance(f_as.value, ast.Call):
                    func_name = self._get_func_name(f_as.value.func)
                    for target in f_as.targets:
                        target_name = self._get_func_name(target)
                        funcs_store_vars[target_name] = func_name
            funcs_info[f.name]["store_vars_calls"] = funcs_store_vars
            nested_definitions = [node for node in ast.walk(f) if isinstance(node, ast.FunctionDef)]
            for nested in nested_definitions:
                if f.name == nested.name:
                    nested_definitions.remove(nested)
            funcs_info[f.name]["functions"] = self._f_definitions(nested_definitions)

        return funcs_info

    def _get_func_name(self, func):
        func_name = ""
        if isinstance(func, ast.Name):
            return func.id

        elif isinstance(func, ast.Attribute):
            attr = ""
            attr += func.attr
            module = func.value
            while isinstance(module, ast.Attribute):
                attr = module.attr + "." + attr
                module = module.value

            # the module is not longer an ast.Attribute
            # entering here in case the module is a Name
            if isinstance(module, ast.Name):
                try:
                    func_name = module.id + "." + attr
                except:
                    pass
                return func_name

            # entering here in case the module is a Call
            # recursively!
            elif isinstance(module, ast.Call):
                try:
                    func_name = self._get_func_name(module.func) + "()." + attr
                except:
                    pass
                return func_name

            # the module is a subscript
            # recursively!
            elif isinstance(module, ast.Subscript):
                # ast.Subscripts
                try:
                    func_name = self._get_func_name(module.value)
                    if not func_name:
                        func_name = "[]." + attr
                    else:
                        func_name = func_name + "[]." + attr
                except:
                    pass
                return func_name
            else:
                return func_name

    def _dfs(self, extend, rest_call_name, renamed, classes_info, renamed_calls):
        for ext in extend:
            if ext in classes_info:
                if rest_call_name in classes_info[ext]["methods"]:
                    renamed_calls.append(self.fileInfo["fileNameBase"] + "." + ext + "." + rest_call_name)
                    renamed = 1
                    return renamed
                else:
                    extend = classes_info[ext]["extend"]
                    renamed = self._dfs(extend, rest_call_name, renamed, classes_info, renamed_calls)
                    if renamed:
                        break
            elif hasattr(ext, rest_call_name):
                renamed_calls.append(ext + "." + rest_call_name)
                renamed = 1
                return renamed
            else:
                extend = classes_info[ext]["extend"]
                renamed = self._dfs(extend, rest_call_name, renamed, classes_info, renamed_calls)
                if renamed:
                    break
        return renamed

    def _fill_call_name(self, funct_def_info, classes_info, class_name="", extend=[], body=0):
        for funct in funct_def_info:
            renamed_calls = []
            f_store_vars = funct_def_info[funct]["store_vars_calls"]
            for call_name in funct_def_info[funct]["calls"]:
                renamed = 0
                module_call_name = call_name.split(".")[0]
                rest_call_name = call_name.split(".")[1:]
                rest_call_name = '.'.join(rest_call_name)

                # We have to change the name of the calls and modules if we have
                # the module stored as a variable in store_vars_calls
                for key, val in f_store_vars.items():
                    if module_call_name == key:
                        module_call_name = val
                        call_name = module_call_name + "." + rest_call_name
                        break

                # check if we are calling to the constructor of a class
                # in that case, add fileNameBase and __init__
                if call_name in classes_info:
                    renamed_calls.append(self.fileInfo["fileNameBase"] + "." + call_name + ".__init__")

                # check if we are calling "self" or  the module is a variable containing "self"
                elif "self" in module_call_name:
                    renamed_calls.append(self.fileInfo["fileNameBase"] + "." + class_name + "." + rest_call_name)

                elif "super()" in module_call_name and extend:
                    # dealing with Multiple Inheritance
                    # implemented depth first search algorithm
                    renamed = self._dfs(extend, rest_call_name, renamed, classes_info, renamed_calls)
                    if not renamed:
                        renamed_calls.append(call_name)
                else:
                    if rest_call_name:
                        rest_call_name = "." + rest_call_name
                    else:
                        rest_call_name = ""

                    for dep in self.depInfo:
                        if dep["import"] == module_call_name:
                            if dep["from_module"]:
                                renamed = 1
                                renamed_calls.append(dep["from_module"] + "." + call_name)
                                break
                            else:
                                renamed = 1
                                renamed_calls.append(call_name)

                        elif dep["alias"]:
                            if dep["alias"] == module_call_name:
                                if dep["from_module"]:
                                    renamed = 1
                                    renamed_calls.append(dep["from_module"] + "." + dep["import"] + rest_call_name)
                                    break
                                else:
                                    renamed = 1
                                    renamed_calls.append(dep["import"] + rest_call_name)
                                    break
                            else:
                                pass

                    if not renamed:
                        # checking if the function has been imported "from module import *"
                        for dep in self.depInfo:
                            if dep["import"] == call_name:
                                if dep["from_module"]:
                                    renamed = 1
                                    renamed_calls.append(dep["from_module"] + "." + call_name)
                                    break
                                else:
                                    pass
                            else:
                                pass

                        if not renamed:
                            # check if the call is a function of the current module
                            if call_name in funct_def_info.keys():
                                renamed = 1
                                renamed_calls.append(self.fileInfo["fileNameBase"] + "." + call_name)
                            else:
                                pass

                            if not renamed:
                                if not body:
                                    for inter_f in funct_def_info:
                                        if call_name in funct_def_info[inter_f]["functions"].keys():
                                            renamed = 1
                                            if class_name:
                                                renamed_calls.append(self.fileInfo[
                                                                         "fileNameBase"] + "." + class_name + "." + inter_f + "." + call_name)
                                                break
                                            else:
                                                renamed_calls.append(
                                                    self.fileInfo["fileNameBase"] + "." + inter_f + "." + call_name)
                                                break
                                        else:
                                            pass
                                if not renamed:
                                    if module_call_name and rest_call_name and self.fileInfo[
                                        "fileNameBase"] not in call_name:
                                        rest_call_name = rest_call_name.split(".")[1]
                                        if module_call_name in classes_info and rest_call_name in \
                                                classes_info[module_call_name]["methods"].keys():
                                            renamed = 1
                                            renamed_calls.append(self.fileInfo["fileNameBase"] + "." + call_name)
                                        elif module_call_name in classes_info:
                                            renamed = self._dfs(classes_info[module_call_name]["extend"], rest_call_name,
                                                                renamed, classes_info, renamed_calls)
                                            if renamed:
                                                renamed_calls.append(self.fileInfo["fileNameBase"] + "." + call_name)
                                            else:
                                                pass
                                        else:
                                            renamed = 1
                                            renamed_calls.append(call_name)
                                    else:
                                        pass

                                    if not renamed:
                                        if "super" != call_name:
                                            renamed_calls.append(call_name)
                                        else:
                                            pass
            funct_def_info[funct]["calls"] = renamed_calls
        return funct_def_info

    def _get_ids(self, elt):
        """_get_ids extracts identifiers if present. 
         If not return None
        :param self self: represent the instance of the class
        :param ast.node elt: AST node
        :return list: list of identifiers
        """
        if isinstance(elt, (ast.List,)) or isinstance(elt, (ast.Tuple,)):
            # For tuple or list get id of each item if item is a Name
            return [x.id for x in elt.elts if isinstance(x, (ast.Name,))]
        if isinstance(elt, (ast.Name,)):
            return [elt.id]

    def _compute_interval(self, node):
        """_compute_interval extract the lines (min and max)
         for a given class, function or method.
        :param self self: represent the instance of the class
        :param ast.node node: AST node
        :return set: min and max lines
        """
        min_lineno = node.lineno
        max_lineno = node.lineno
        for node in ast.walk(node):
            if hasattr(node, "lineno"):
                min_lineno = min(min_lineno, node.lineno)
                max_lineno = max(max_lineno, node.lineno)
        return {"min_lineno": min_lineno, "max_lineno": max_lineno + 1}

    def _formatFlow(self, s):
        """_formatFlow reformats the control flow output
        as a text.
        :param self self: represent the instance of the class
        :param cfg_graph s: control flow graph 
        :return str: cfg formated as a text
        """

        result = ""
        shifts = []  # positions of opening '<'
        pos = 0  # symbol position in a line
        next_is_list = False

        def is_next_list(index, maxIndex, buf):
            if index == maxIndex:
                return False
            if buf[index + 1] == '<':
                return True
            if index < maxIndex - 1:
                if buf[index + 1] == '\n' and buf[index + 2] == '<':
                    return True
            return False

        max_index = len(s) - 1
        for index in range(len(s)):
            sym = s[index]
            if sym == "\n":
                last_shift = shifts[-1]
                result += sym + last_shift * " "
                pos = last_shift
                if index < max_index:
                    if s[index + 1] not in "<>":
                        result += " "
                        pos += 1
                continue
            if sym == "<":
                if not next_is_list:
                    shifts.append(pos)
                else:
                    next_is_list = False
                pos += 1
                result += sym
                continue
            if sym == ">":
                shift = shifts[-1]
                result += '\n'
                result += shift * " "
                pos = shift
                result += sym
                pos += 1
                if is_next_list(index, max_index, s):
                    next_is_list = True
                else:
                    del shifts[-1]
                    next_is_list = False
                continue
            result += sym
            pos += 1
        return result


def create_output_dirs(output_dir):
    """create_output_dirs creates two subdirectories
       to save the results. ControlFlow to save the
       cfg information (txt and PNG) and JsonFiles to
       save the aggregated json file with all the information
       extracted per file. 
       :param str output_dir: Output Directory in which the new subdirectories
                          will be created.
       """

    control_flow_dir = os.path.abspath(output_dir) + "/control_flow"

    if not os.path.exists(control_flow_dir):
        print("Creating cf %s" % control_flow_dir)
        os.makedirs(control_flow_dir)
    else:
        pass
    json_dir = output_dir + "/json_files"

    if not os.path.exists(json_dir):
        print("Creating jsDir:%s" % json_dir)
        os.makedirs(json_dir)
    else:
        pass
    return control_flow_dir, json_dir


@click.command()
@click.option('-i', '--input_path', type=str, required=True, help="input path of the file or directory to inspect.")
@click.option('-f', '--fig', type=bool, is_flag=True, help="activate the control_flow figure generator.")
@click.option('-o', '--output_dir', type=str, default="output_dir",
              help="output directory path to store results. If the directory does not exist, the tool will create it.")
@click.option('-ignore_dir', '--ignore_dir_pattern', multiple=True, default=[".", "__pycache__"],
              help="ignore directories starting with a certain pattern. This parameter can be provided multiple times "
                   "to ignore multiple directory patterns.")
@click.option('-ignore_file', '--ignore_file_pattern', multiple=True, default=[".", "__pycache__"],
              help="ignore files starting with a certain pattern. This parameter can be provided multiple times "
                   "to ignore multiple file patterns.")
@click.option('-r', '--requirements', type=bool, is_flag=True, help="find the requirements of the repository.")
@click.option('-html', '--html_output', type=bool, is_flag=True,
              help="generates an html file of the DirJson in the output directory.")
@click.option('-cl', '--call_list', type=bool, is_flag=True,
              help="generates the call list in a separate json file.")
def main(input_path, fig, output_dir, ignore_dir_pattern, ignore_file_pattern, requirements, html_output, call_list):
    if (not os.path.isfile(input_path)) and (not os.path.isdir(input_path)):
        print('The file or directory specified does not exist')
        sys.exit()

    if os.path.isfile(input_path):
        cf_dir, json_dir = create_output_dirs(output_dir)
        code_info = CodeInspection(input_path, cf_dir, json_dir, fig)

        # Generate the call list of a file
        if call_list:
            call_list = call_list_file(code_info)
            call_file_html = json_dir + "/CallGraph.html"
            if html_output:
                generate_output_html(call_list, call_file_html)
        if html_output:
            output_file_html = json_dir + "/FileInfo.html"
            f = open(code_info.fileJson[1])
            data = json.load(f)
            generate_output_html(data, output_file_html)

    else:
        dir_info = {}
        for subdir, dirs, files in os.walk(input_path):

            for ignore_d in ignore_dir_pattern:
                dirs[:] = [d for d in dirs if not d.startswith(ignore_d)]
            for ignore_f in ignore_file_pattern:
                files[:] = [f for f in files if not f.startswith(ignore_f)]
            # print(files)
            for f in files:
                if ".py" in f and not f.endswith(".pyc"):
                    try:
                        path = os.path.join(subdir, f)
                        out_dir = output_dir + "/" + os.path.basename(subdir)
                        cf_dir, json_dir = create_output_dirs(out_dir)
                        code_info = CodeInspection(path, cf_dir, json_dir, fig)
                        if out_dir not in dir_info:
                            dir_info[out_dir] = [code_info.fileJson[0]]
                        else:
                            dir_info[out_dir].append(code_info.fileJson[0])
                    except:
                        print("Error when processing " + f + ": ", sys.exc_info()[0])
                        continue

        # Generate the call list of the Dir
        if call_list:
            call_list = call_list_dir(dir_info)
            call_file_html = output_dir + "/call_graph.html"
            if html_output:
                generate_output_html(call_list, call_file_html)
        # Note:1 for visualising the tree, nothing or 0 for not.
        if requirements:
            dir_requirements = find_requirements(input_path)
            dir_info["requirements"] = dir_requirements

        dir_info["directory_tree"] = directory_tree(input_path, ignore_dir_pattern, ignore_file_pattern, 1)
        dir_info["software_invocation"] = software_invocation(dir_info, input_path)
        json_file = output_dir + "/directory_info.json"
        pruned_json = prune_json(dir_info)
        with open(json_file, 'w') as outfile:
            json.dump(pruned_json, outfile)
        print_summary(dir_info)
        if html_output:
            output_file_html = output_dir + "/directory_info.html"
            generate_output_html(pruned_json, output_file_html)


if __name__ == "__main__":
    main()
