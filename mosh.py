#!/usr/bin/env python3

import os
import argparse
import subprocess

try:
    from tqdm import tqdm
except ImportError:
    tqdm = None

parser = argparse.ArgumentParser()
parser.add_argument('input_video', type=str, help='File to be moshed')
parser.add_argument('--start_frame', '-s', default=0, type=int, help='start frame of the mosh')
parser.add_argument('--end_frame', '-e', default=-1, type=int, help='end frame of the mosh')
parser.add_argument('--fps', '-f', default=30, type=int, help='fps to convert initial video to')
parser.add_argument('-o', default='moshed.mp4', type=str, dest='output_video', help='output file for the moshed video')
parser.add_argument('--delta', '-d', default=0, type=int, help='number of delta frames to repeat')
args = parser.parse_args().__dict__

input_video = args['input_video']
start_frame = args['start_frame']
end_frame = args['end_frame']
fps = args['fps']
delta = args['delta']
output_video = args['output_video']

input_avi = 'datamoshing_input.avi'
output_avi = 'datamoshing_output.avi'

frame_start = b'\x30\x30\x64\x63'
iframe = b'\x00\x01\xB0'
pframe = b'\x00\x01\xB6'


def convert_input():
    print(f">> Converting {input_video} to AVI...")
    subprocess.call('ffmpeg -loglevel error -y -i ' + input_video +
                    ' -crf 0 -pix_fmt yuv420p -bf 0 -g 60 -r ' + str(fps) + ' ' +
                    input_avi, shell=True)


def stream_frames(file_path):
    """Generator to yield frames while updating progress bar."""
    file_size = os.path.getsize(file_path)
    pbar = tqdm(total=file_size, unit='B', unit_scale=True, desc=">> Moshing") if tqdm else None

    with open(file_path, 'rb') as f:
        chunk_size = 1024 * 1024
        remainder = b''

        data = f.read(chunk_size)
        if pbar: pbar.update(len(data))
        header_end = data.find(frame_start)
        if header_end != -1:
            yield data[:header_end]
            remainder = data[header_end:]

        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                if remainder: yield remainder
                break

            if pbar: pbar.update(len(chunk))
            combined = remainder + chunk
            parts = combined.split(frame_start)

            for part in parts[:-1]:
                if part: yield frame_start + part
            remainder = parts[-1]

    if pbar: pbar.close()


def cleanup():
    if os.path.exists(input_avi): os.remove(input_avi)
    if os.path.exists(output_avi): os.remove(output_avi)
    exit(0)


def mosh():
    frames_gen = stream_frames(input_avi)
    try:
        header = next(frames_gen)
    except StopIteration:
        return

    with open(output_avi, 'wb') as out_file:
        out_file.write(header)
        repeat_frames = []
        video_frame_count = 0

        for frame in frames_gen:
            is_iframe = iframe in frame[0:30]
            is_pframe = pframe in frame[0:30]

            if is_iframe or is_pframe:
                video_frame_count += 1

            if not delta:
                if start_frame <= video_frame_count <= end_frame and is_iframe:
                    continue
                out_file.write(frame)
            else:
                if video_frame_count < start_frame or (end_frame != -1 and video_frame_count > end_frame):
                    out_file.write(frame)
                else:
                    if len(repeat_frames) < delta:
                        if not is_iframe:
                            repeat_frames.append(frame)
                        out_file.write(frame)
                    else:
                        out_file.write(repeat_frames[video_frame_count % delta])


convert_input()
mosh()

print(f">> Exporting to {output_video}...")
subprocess.call('ffmpeg -loglevel error -y -i ' + output_avi +
                ' -crf 18 -pix_fmt yuv420p -vcodec libx264 -acodec aac -r ' + str(fps) + ' ' +
                output_video, shell=True)

cleanup()
