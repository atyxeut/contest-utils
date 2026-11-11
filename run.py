# SPDX-FileCopyrightText: 2026 atyxeut <atyxeut@outlook.com>
# SPDX-License-Identifier: GPL-3.0-or-later

import argparse
import subprocess
import sys
import time
from enum import Enum
from pathlib import Path


class Mode(Enum):
    TEST = 0
    DIFF = 1
    GENERATE = 2


default_testdata_dir = Path("test/default")
log_path = Path("test/log.txt")

parser = argparse.ArgumentParser(add_help=False)

# > run.py -m -i testdata_dir
# 1. execute preprocessor/pp.py (can remove -m, see pp.py for -m usage)
# 2. iterate .in/.out pairs in `testdata_dir`, use the content of .in as input, test if the output of sol.cpp is the
#    same as the content of xxx.out (after removing trailing white characters), write the information into `log_path`
# 3. -i is only available in test mode
parser.add_argument("-m", "--multiple_tests", action="store_true")
parser.add_argument("-i", "--input_dir", metavar="testdata_dir", default=None, type=str)

mutex_args = parser.add_mutually_exclusive_group()

# > run.py -m -d count -o testdata_dir
# 1. preprocess
# 2. loop A, B `count` times:
#   A. generate a piece of data using gen.cpp
#   B. let sol.cpp and std.cpp both take this data as input, compare the output, if the two outputs differ, save the
#      input and the output of std.cpp into `testdata_dir`, then write the information into `log_path`, and terminate
#      the loop
mutex_args.add_argument("-d", "--diff", metavar="count", nargs="?", const=100, type=int)

# > run.py -m -g count -o testdata_dir
# 1. preprocess
# 2. loop `count` times:
#    gen.cpp generates inputs, then sol.cpp generates corresponding outputs, save the them into testdata_dir
mutex_args.add_argument("-g", "--generate", metavar="count", type=int)

parser.add_argument("-o", "--output_dir", metavar="testdata_dir", default=None, type=str)

argv = parser.parse_args()

exe_dir_path = Path(Path("build/exe_dir.txt").read_text().rstrip())
sol_exe_path = exe_dir_path / "sol"
std_exe_path = exe_dir_path / "std"
gen_exe_path = exe_dir_path / "gen"


def execute(exe_path: Path, input_data: str):
    time_point_begin = time.perf_counter()
    process = subprocess.run([exe_path], text=True, input=input_data, capture_output=True, check=False)
    time_point_end = time.perf_counter()
    return [process.stdout, process.stderr, 1e3 * (time_point_end - time_point_begin)]


def compare_output(usr_out: str, std_out: str):
    def preprocess(content: str):
        out = content.rstrip().split("\n")
        for i in range(len(out)):
            out[i] = out[i].rstrip()
        return out

    usr = preprocess(usr_out)
    std = preprocess(std_out)
    is_same = len(usr) == len(std)
    result = ""
    align_size = max(len(line) for line in usr)

    def align(content: str):
        if not content:
            content += " "
        return content + " <" + "-" * max(0, align_size - len(content)) + "-- "

    usr_len = len(usr)
    std_len = len(std)
    larger_len = max(usr_len, std_len)
    for i in range(larger_len):
        if i >= usr_len:
            result += align("") + std[i] + "\n"
        elif i >= std_len:
            result += align(usr[i]) + "redundant\n"
        else:
            if usr[i] == std[i]:
                result += std[i] + "\n"
            else:
                is_same = False
                result += align(usr[i]) + std[i] + "\n"

    return [is_same, result]


def normal_mode(tested_cnt: int = 0):
    subprocess.run(["xmake"], check=False)
    print(f"testing... see {log_txt_path}")

    for testcase in testdata_dir_path.glob("*.in"):
        testcase_in_file_path = testdata_dir_path / f"{testcase.stem}.in"
        testcase_out_file_path = testdata_dir_path / f"{testcase.stem}.out"

        if testcase_in_file_path.read_text().rstrip() == "":
            continue

        tested_cnt += 1

        sol_output, sol_errout, sol_execution_time = execute(sol_exe_path, testcase_in_file_path.read_text())
        std_output = testcase_out_file_path.read_text()

        (testdata_dir_path / f"{testcase.stem}.err").write_text(sol_errout)

        is_same, comp_result = compare_output(sol_output, std_output)

        if is_same:
            with log_txt_path.open(mode="a") as log_file:
                log_file.write(
                    f"test {tested_cnt} ({testcase_in_file_path.name}), {sol_execution_time:.3f}ms, passed\n"
                )
        else:
            with log_txt_path.open(mode="a+") as log_file:
                log_file.seek(0)
                content = log_file.readlines()
                log_file.seek(2)
                if content and content[-1] != "\n":
                    log_file.write("\n")
                log_file.write(
                    f"test {tested_cnt} ({testcase_in_file_path.name}), "
                    f"{sol_execution_time:.3f}ms, failed:\n{comp_result}\n"
                )

    print("done")


def diff_mode(no_difference: bool = True):
    # must ensure that none of sol.cpp, std.cpp and gen.cpp is empty
    subprocess.run(["xmake", "build", "sol"], check=False)
    subprocess.run(["xmake", "build", "std"], check=False)
    subprocess.run(["xmake", "build", "gen"], check=False)
    print(f"testing... see {log_txt_path}")

    for _ in range(int(argv.diff)):

        def get_new_test_data_stem():
            number_stems = [int(path.stem) for path in testdata_dir_path.glob("*.in") if path.stem.isdigit()]
            if number_stems:
                absent = set(range(1, max(number_stems) + 2)) - set(number_stems)
                return str(min(absent))
            return "1"

        new_test_data_stem = get_new_test_data_stem()
        new_test_data = subprocess.run([gen_exe_path], text=True, stdout=subprocess.PIPE, check=False).stdout
        sol_output, _, _ = execute(sol_exe_path, new_test_data)
        std_output, _, _ = execute(std_exe_path, new_test_data)

        def save_data(dir=testdata_dir_path, stem=new_test_data_stem, input=new_test_data, output=std_output):
            (dir / (stem + ".in")).write_text(input)
            (dir / (stem + ".out")).write_text(output)
            (dir / (stem + ".err")).touch()

        if argv.save:
            save_data()

        is_same, comp_result = compare_output(sol_output, std_output)
        if not is_same:
            no_difference = False
            with log_txt_path.open(mode="a") as log_file:
                log_file.write(f"different on {new_test_data_stem}.in:\n{comp_result}\n")
            if not argv.save:
                save_data()
                break

    if no_difference:
        log_txt_path.write_text("no difference\n")

    print("done")


def resolve_mode():
    if argv.diff is not None or argv.generate is not None:
        if argv.input_dir is not None:
            parser.error("-i/--input_dir is only available in test mode")
        if argv.output_dir is None:
            argv.output_dir = default_testdata_dir
        else:
            argv.output_dir = Path(argv.output_dir)

    if argv.diff is not None:
        if argv.diff > 0:
            return Mode.DIFF
        else:
            parser.error("-d/--diff count must be positive")
    elif argv.generate is not None:
        if argv.generate > 0:
            return Mode.GENERATE
        else:
            parser.error("-g/--generate count must be positive")
    else:
        if argv.output_dir is not None:
            parser.error("-o/--output_dir is useless in test mode")
        if argv.input_dir is None:
            argv.input_dir = default_testdata_dir
        else:
            argv.input_dir = Path(argv.input_dir)
        return Mode.TEST


def main():
    mode = resolve_mode()

    pp_args = []
    if argv.multiple_tests:
        pp_args.append("-m")
    subprocess.run([sys.executable, "preprocessor/pp.py"] + pp_args, check=True)
    log_path.write_text("")

    if mode == Mode.TEST:
        test()
    elif mode == Mode.DIFF:
        diff()
    elif mode == Mode.GENERATE:
        generate()


if __name__ == "__main__":
    main()
