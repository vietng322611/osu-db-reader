import win32security
import getpass
import winreg
import os
import struct

#--------------------------------------------------Types-----------------------------------------------

'''
Count and size each:
7 Byte: 1 byte
7 Boolean: 1 byte
5 Short: 2 bytes
7 Int: 4 bytes
5 Single: 4 bytes
3 Long: 8 bytes
1 Double: 8 bytes
13 String: 1 byte indicates presence, 1 bytes indicates size, then the aforementioned string
4 Int-Double pair+: 1 int indicates number, then the aforementioned pairs
1 Timing point+: 1 int indicates number, then the aforementioned timing points
'''

class Beatmap:
    def __init__(self) -> None:
        self.name: str
        self.set_id: int
        self.diff_id: int
        self.filename: str
        self.checksum: str

    def __repr__(self) -> str:
        return "ID=%s\nChecksum=%s\nFilename=%s\n" % (self.id, self.checksum, self.filename)

#----------------------------------------------Main program--------------------------------------------

def load_db(path: str) -> bytes:
    try:
        with open(path, "rb") as f:
            osudb = f.read()
        return osudb
    except OSError as e:
        print("An error occurred: %s" % e.strerror)
        print("Can't open osu!.db! Please check if the path is correct.\nExisting.....")
        raise e

def decode_uleb128(osudb: bytes, index: int) -> tuple[int, int]:
    result = '0b0'
    bin_str = bin(osudb[index])
    next_index = index + 1
    for _ in range(3):
        if (len(bin_str) != 10): break

        result = bin_str + result[3:]
        bin_str = bin(osudb[next_index])
        next_index += 1

    result = bin_str + result[3:]
    return (int(result, 2), next_index)

def read_string(osudb: bytes, index: int) -> tuple[bytes, int]:
    try:
        is_present = osudb[index]
        if (is_present == 0): return (None, 1)

        length, str_idx = decode_uleb128(osudb, index+1)
        return (osudb[str_idx : str_idx+length], str_idx+length)
    except Exception as e:
        raise e

def skip_custom_types(osudb: bytes, index: int) -> int:
    current_idx = index
    try:
        for _ in range(4):
            current_idx += struct.unpack("<i", osudb[current_idx : current_idx+4])[0]*14 + 4
        current_idx += 4*3
        current_idx += struct.unpack("<i", osudb[current_idx : current_idx+4])[0]*17 + 4
    except Exception as e:
        raise e

    return current_idx

def read_db() -> list[Beatmap]:
    osudb_path = os.path.expandvars("%userprofile%").replace("\\", "/") + "/AppData/Local/osu!/osu!.db"

    sid = win32security.LookupAccountName(None, getpass.getuser())[0]
    key_path = win32security.ConvertSidToStringSid(sid) + "_Classes\\osu\\Shell\\Open\\Command"
    try:
        key = winreg.OpenKey(winreg.HKEY_USERS, key_path)

        osudb_path: str = winreg.EnumValue(key, 0)[1]
        osudb_path = osudb_path.split('\"')[1].replace(".exe", ".db")

        key.Close()
    except OSError:
        pass

    usr_input = input(f"Is this your osu!.db path: {osudb_path}\nIf yes, press enter. If no, enter your osu!.db path here: ")
    if (usr_input != ''):
        osudb_path = usr_input
    osudb = load_db(osudb_path)

    bm_list: list[Beatmap] = []
    try:
        beatmap_offset = read_string(osudb, 17)[1]
        beatmap_count = struct.unpack("<i", osudb[beatmap_offset : beatmap_offset+4])[0]
        data_offset = beatmap_offset + 4

        while(beatmap_count):
            bm = Beatmap()
            tmp_offset = data_offset

            for i in range(4):
                obj_cnt = 1
                match i:
                    case 0:
                        obj_cnt = 9
                    case 1:
                        obj_cnt = 2
                        tmp_offset = skip_custom_types(osudb, tmp_offset + 39)
                        bm.diff_id = struct.unpack("<i", osudb[tmp_offset : tmp_offset+4])[0]
                        bm.set_id = struct.unpack("<i", osudb[tmp_offset+4 : tmp_offset+8])[0]
                        tmp_offset += 23
                    case 2:
                        tmp_offset += 2
                    case 3:
                        tmp_offset += 10

                for _ in range(obj_cnt):
                    _tmp, _next = read_string(osudb, tmp_offset)
                    if (_tmp == None):
                        tmp_offset += 1
                        continue

                    if (_ == 2): bm.name = _tmp.decode()
                    if (_ == 7): bm.checksum = _tmp.decode()
                    if (_ == 8): bm.filename = _tmp.decode()
                    
                    tmp_offset = _next

                if (i == 3): data_offset = tmp_offset + 18

            bm_list.append(bm)
            beatmap_count -= 1
    except OSError as e:
        print("An error occurred: %s" % e.strerror)
        print("Can't continue, abortting.....")

    return bm_list