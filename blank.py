import subprocess as sp
sp.run('ffmpeg -t 3600 -s 1920x1080 -f rawvideo -pix_fmt rgb24 -r 25 -i /dev/zero blank_0.mp4')
