import subprocess
import re

info_chunk_pattern = re.compile(r"Chunk \w{1,4}")

info_duration_pattern = re.compile(r"\s{2}Duration: \d+\s*")


def get_frames_duration(file_name):
    commandline = ['webpinfo', file_name]
    output = subprocess.check_output(commandline)
    output = str(output, "utf-8")

    current_chunk = ''
    duration = []
    for line in output.splitlines():
        if info_chunk_pattern.search(line) is not None:
            current_chunk = info_chunk_pattern.findall(line)[0][6:]
        elif current_chunk == 'ANMF' and info_duration_pattern.search(line):
            duration.append(int(re.findall("\d+", line)[0]))
    return duration
