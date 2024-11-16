from zipfile import ZipFile
from tqdm import tqdm
from os.path import basename
from pathlib import Path
from reader import Beatmap, read_db
from datetime import datetime
from time import sleep

import tempfile
import requests
import argparse
import concurrent.futures

mirrors = {
    "nerinyan.moe": "https://api.nerinyan.moe/d/{}",
    "beatconnect.io": "https://beatconnect.io/b/{}"
}

dled = []
done = []
failed = []
limit_reached = False
wait_time = 0

def save_log():
    time = datetime.now().strftime("%d%m%Y")
    with open(f"{time} - log.txt", "w") as f:
        f.write(f"Succeed count: {len(done)}\n")
        for i in done: f.write(i + "\n")

        f.write(f"\nFailed count: {len(failed)}\n")
        for i in failed: f.write(i + "\n")

def start_downloader(bm: Beatmap, path: Path):
    global limit_reached, wait_time
    success = False
    for m in mirrors:
        if (limit_reached): pass
        url = mirrors[m].format(bm.set_id)
        print("Trying to download #{0} from {1}".format(bm.set_id, m))

        headers = {'User-Agent': 'Mozilla/5.0'}
        resp = requests.get(url, stream=True, headers=headers)
        if (resp.headers["X-RateLimit-Remaining"] == 0):
            limit_reached = True
            wait_time = resp.headers["X-Retry_After"]
        if resp.status_code == 200:
            total = int(resp.headers.get('content-length', 0))
            name_osz = resp.headers.get("Content-Disposition").split("filename=")[1].strip('"')
            filename = path.joinpath(name_osz)

            with open(filename, 'wb') as file, tqdm(
                desc=name_osz,
                total=total,
                unit='iB',
                unit_scale=True,
                unit_divisor=1024,
            ) as bar:
                for data in resp.iter_content(chunk_size=1024):
                    size = file.write(data)
                    bar.update(size)

            if filename.exists(): print("Downloaded #{}".format(bm.set_id))
            else: break

            dled.append(filename)
            done.append(bm.name)

            success = True
            break
        
    if not success:
        failed.append(bm.name)
        print("Failed to download #{}! It probably does not exist on the mirrors.\n"
        "Please manually download the beatmap from osu.ppy.sh!".format(bm.set_id))


def download(beatmaps: list[Beatmap], path, name: str):
    # use temp_dir if no path specified
    if len(path) == 0:
        temp_dir = tempfile.TemporaryDirectory()
        print("Using temporary directory {}".format(temp_dir.name))
        path = Path(temp_dir.name)
    else:
        path = Path(path)
        
        if not path.exists(): raise Exception("The specified path {} does not exist!".format(path)) 

    # tip for download getting stuck
    print("\nPress Ctrl + C if download gets stuck for too long.\n")

    futures = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        for bm in beatmaps:
            futures.append(executor.submit(start_downloader, bm, path))
        for future in futures:
            if (limit_reached):
                sleep(wait_time)
                limit_reached = False
            future.result()

    print("\nFinished downloading!")

    add_to_zip(dled, name)

    try: temp_dir.cleanup()
    except: pass

    save_log()

def add_to_zip(paths, name):
    print("Adding to zip....")
    with ZipFile(name, 'w') as z:
        for f in paths:
            z.write(f, basename(f))

def filter_beatmapset(beatmaps: list[Beatmap]) -> list[Beatmap]:
    ret = []
    existed = 0
    for bm in beatmaps:
        if (bm.set_id == existed): continue
        ret.append(bm)
        existed = bm.set_id
    return ret

ap = argparse.ArgumentParser(description='Download beatmaps from a list of links.')

ap.add_argument("-n", "--name", required=True, metavar="example.zip",
   help="the name of the zip file to be created")
ap.add_argument("-o", "--out", required=False, metavar="D:\\Songs\\", default="",
   help="the directory where downloaded beatmaps are to be saved, "
   "use this if you don't want the beatmaps to be deleted after zipping (make sure the folder exists)")
args = vars(ap.parse_args())

beatmaps = filter_beatmapset(read_db())
print(f"You have {len(beatmaps)} beatmaps in osu!. It's would take a lot of time if there are too many maps")
count = int(input("Do you want to download only a part of it? If no, press enter. If yes, enter the amount here: "))
if (count > len(beatmaps) or count <= 0):
    print("Invaild number of maps! Abortting.....")
    exit(0)
beatmaps = beatmaps[:count]

print(f"Downloading {count} maps.....")
download(beatmaps, args["out"], args["name"])

print("Done!")
