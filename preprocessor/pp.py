# SPDX-FileCopyrightText: 2026 atyxeut <atyxeut@outlook.com>
# SPDX-License-Identifier: GPL-3.0-or-later

import argparse
import re
import subprocess
from pathlib import Path

parser = argparse.ArgumentParser(add_help=False)

# > pp.py -m
# expand #include <***.hpp> directives in sol.cpp, output the result into sub.cpp, then add `#define NDEBUG` at the beginning of sub.cpp
# if -m is presented, add `#define MULTIPLE_TESTS 1` at the beginning of sub.cpp, see template/sol.cpp for the usage of this macro
parser.add_argument("-m", "--multiple_tests", action="store_true")

argv = parser.parse_args()

sol_cpp_path = Path("sol.cpp")
sub_cpp_path = Path("sub.cpp")

custom_header_include_path = Path("include").resolve()
header_match_pattern = re.compile(r"^#include\s*<(.+)>\s*\n")  # match `#include <xxx>`

headers_to_ignore = ["bits/stdc++.h"]
lines_to_ignore = ["#pragma once", "using namespace std;"]


def expand(cur_file_path: Path):
    with cur_file_path.open() as src_file:
        code = src_file.readlines()

    if len(code) == 0:
        return ""

    for i in range(len(code)):
        if code[i].rstrip() in lines_to_ignore:
            code[i] = ""
            continue

        # avoid duplicate `#include <xxx>`
        header_match = header_match_pattern.match(code[i])
        if header_match:
            header_name = header_match.group(1)
            if header_name in headers_to_ignore:
                code[i] = ""
            else:
                if not header_name.endswith(".hpp"):
                    # remove all standard headers, only include <bits/stdc++.h> to reduce code size
                    code[i] = ""
                    headers_to_ignore.append(header_name)
                else:
                    headers_to_ignore.append(header_name)
                    custom_header_path = custom_header_include_path / header_name
                    code[i] = expand(custom_header_path)

    return ("".join(code) + ("" if cur_file_path == sol_cpp_path.resolve() else "\n")).lstrip()


chunks_to_ignore = [("assert(", ";")]


def remove_unecessary_chunks(code: str):
    code = bytearray(code, "utf-8")

    for chunk in chunks_to_ignore:
        begin = bytes(chunk[0], "utf-8")
        end = bytes(chunk[1], "utf-8")
        i = code.find(begin, 0)
        while i != -1:
            while code[i] != end:
                code[i] = ord(" ")
                i += 1
            i = code.find(begin, i + 1)

    return code.decode("utf-8")


def remove_unecessary_white_characters(code: list):
    char_set = ";,:?.{}[]()<>=!&|^+-*/%"
    for i in range(len(code)):
        if code[i] == "\n":
            code[i] = ""
        elif code[i] in char_set:
            if i - 1 >= 0 and code[i - 1] == " ":
                code[i - 1] = ""
            if i + 1 < len(code) and code[i + 1] == " ":
                code[i + 1] = ""
    return "".join(code) + "\n\n"


def main():
    expanded_code = expand(sol_cpp_path.resolve())

    def get_main_fn_end():
        left_brace_cnt = 1
        pos = expanded_code.find("{", expanded_code.find("int main()")) + 1
        while left_brace_cnt != 0:
            if expanded_code[pos] == "{":
                left_brace_cnt += 1
            elif expanded_code[pos] == "}":
                left_brace_cnt -= 1
            pos += 1
        return pos

    main_fn_end_pos = get_main_fn_end()
    upper = remove_unecessary_chunks(expanded_code[:main_fn_end_pos])

    macro_defs = "#define NDEBUG\n"
    if argv.multiple:
        macro_defs += "#define IS_ONE_INPUT_MULTIPLE_TESTS 1\n"

    upper_code_before_pp_path = Path("build/upper_code_before_pp.cpp")
    upper_code_before_pp_path.write_text(macro_defs + upper)
    subprocess.run(["g++", "-E", "-P", "-o", sub_cpp_path, upper_code_before_pp_path], check=True)
    subprocess.run(["clang-format", "-style=file:preprocessor/.clang-format-pp", "-i", sub_cpp_path], check=True)
    upper = remove_unecessary_white_characters(list(sub_cpp_path.read_text()))

    beginning = "#include <bits/stdc++.h>\n\n" + "using namespace std;\n\n"
    lib_description = "// library from: https://github.com/atyxeut/contest-utils\n"
    expanded_code = beginning + lib_description + upper + expanded_code[main_fn_end_pos:].lstrip()

    sub_cpp_path.write_text(expanded_code)


if __name__ == "__main__":
    main()
