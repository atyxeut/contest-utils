# SPDX-FileCopyrightText: 2026 atyxeut <atyxeut@outlook.com>
# SPDX-License-Identifier: GPL-3.0-or-later

import argparse
import subprocess
import time
from pathlib import Path

# > run.py
# 1. execute preprocessor/pp.py, -t gcc -r are passed to it, you can choose whether to pass -m
# 2. for every xxx.in/xxx.out pair from `testdata_dir_path`, use the content of xxx.in as input, test if the output of sol.cpp is the same
#    as the content of xxx.out (after removing trailing white characters), write the information into `log_txt_path`
parser = argparse.ArgumentParser(add_help=False)
parser.add_argument("-m", "--multiple", action="store_true")
# > run.py -d count
#                       ↑ 1. can be empty, the default value is 50
#                         2. can be a float, e.g. 1e3
#                         3. must be positive
# do the following things `count` times:
# 1. generate a piece of data using gen.cpp
# 2. let sol.cpp and std.cpp both take this data as input, and compare the output of them, if the two outputs differ, save the input and
#    the output of std.cpp into `testdata_dir_path`, then write the information into `log_txt_path`, and terminate the loop
parser.add_argument("-d", "--diff", metavar="count", nargs="?", const=50, type=float)
# > run.py -d count -s
# -d mode, but loop certainly `count` times, and save every generated data pair
parser.add_argument("-s", "--save", action="store_true")
argv = parser.parse_args()


testdata_dir_path = Path("test/data")
log_txt_path = Path("test/log.txt")


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
        log_file.write(f"test {tested_cnt} ({testcase_in_file_path.name}), {sol_execution_time:.3f}ms, passed\n")
    else:
      with log_txt_path.open(mode="a+") as log_file:
        log_file.seek(0)
        content = log_file.readlines()
        log_file.seek(2)
        if content and content[-1] != "\n":
          log_file.write("\n")
        log_file.write(f"test {tested_cnt} ({testcase_in_file_path.name}), {sol_execution_time:.3f}ms, failed:\n{comp_result}\n")

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


def main():
  pp_args_list = ["-t", "gcc", "-r"]
  if argv.multiple:
    pp_args_list.append("-m")
  subprocess.run(["python3", "preprocessor/pp.py"] + pp_args_list, check=False)

  log_txt_path.write_text("")

  if argv.diff is not None:
    if argv.diff <= 0:
      raise SyntaxError("invalid arguments")
    diff_mode()
  else:
    if argv.save:
      raise SyntaxError("invalid arguments")
    normal_mode()


if __name__ == "__main__":
  main()
