import serial
import unicodedata
import numpy as np
import csv
import cv2
import base64
import time

class CharaZenkaku:
    zenkaku: list
    class cdb:
        ver: int
        jisx: int
        utf8: int
        def __init__(self, ver, jisx, utf8):
            self.ver = int(ver)
            self.jisx = int(jisx, 16)
            self.utf8 = int(utf8, 16)
    
    def __init__(self):
        self.init_zenkaku()
    
    def init_zenkaku(self):
        self.zenkaku = []
        with open("./shinonome16-1.0.4/iso-2022-jp-2004-std.tsv", mode="r", encoding="utf-8", newline='') as f:
            reader = csv.reader(f, delimiter="\t")
            # ignore header 23 lines
            for _ in range(23):
                next(reader)
            for cols in reader:
                try:
                    ver,jisx = cols[0].split("-")
                    utf8 = cols[1].split("+")[1]
                    char = CharaZenkaku.cdb(ver, jisx, utf8)
                    self.zenkaku.append(char)
                except:
                    pass

    def get_img_from_latin(self, char: int):
        ret = None
        ascii = int(char.encode('ascii')[0])
        target_string = "STARTCHAR " + format(ascii, '2x')
        next_string = "ENCODING " + format(ascii, 'd')
        with open("./shinonome16-1.0.4/latin.bdf", mode="r", encoding="utf-8") as f:
            lines = f.readlines()
            for i, line in enumerate(lines):
                if line.startswith(target_string) and lines[i+1].startswith(next_string):
                    ret = np.zeros((16, 8, 3), np.uint8)
                    for j in range(16):
                        line = lines[i+6+j]
                        for bit in range(8):
                            ret[j][bit] = [0,0,0] if line[bit] == "." else [255,255,255]
                    break
        return ret

    def get_img_from_hankaku(self, char: str):
        ret = None
        sjis = int(char.encode('shift_jis')[0])
        target_string = "STARTCHAR   " + format(sjis, '2x')
        with open("./shinonome16-1.0.4/hankaku.bdf", mode="r", encoding="utf-8") as f:
            lines = f.readlines()
            for i, line in enumerate(lines):
                if line.startswith(target_string):
                    ret = np.zeros((16, 8, 3), np.uint8)
                    for j in range(16):
                        line = lines[i+6+j]
                        for bit in range(8):
                            ret[j][bit] = [0,0,0] if line[bit] == "." else [255,255,255]
                    break
        return ret

    def get_img_from_zenkaku(self, char: str):
        ret = None
        for c in self.zenkaku:
            if c.utf8 == ord(char):
                jisx = c.jisx
                break
        if jisx is None:
            return None

        target_string = "STARTCHAR " + format(jisx, '4x')
        with open("./shinonome16-1.0.4/zenkaku.bdf", mode="r", encoding="utf-8") as f:
            lines = f.readlines()
            for i, line in enumerate(lines):
                if line.startswith(target_string):
                    ret = np.zeros((16, 16, 3), np.uint8)
                    for j in range(16):
                        line = lines[i+6+j]
                        for bit in range(16):
                            ret[j][bit] = [0,0,0] if line[bit] == "." else [255,255,255]
                    break
        return ret

    def convert_jisx_to_img(self, char:str):
        ret = None
        match unicodedata.east_asian_width(char):
            case 'Na': # Narrow
                ret = self.get_img_from_latin(char)
            case 'F': # Fullwidth
                ret = self.get_img_from_zenkaku(char)
            case 'W': # Wide
                ret = self.get_img_from_zenkaku(char)
            case 'H': # Halfwidth
                ret = self.get_img_from_hankaku(char)
        return ret

    def search_string(self, string:str):
        marge_image = []
        for chara in string:
            ret = self.convert_jisx_to_img(chara)
            if ret is None:
                continue
            # 画像を結合し左詰めにする
            if len(marge_image) == 0:
                marge_image = ret
            else:
                padding = cv2.imread('./shinonome16-1.0.4/padding.bmp')
                marge_image = cv2.hconcat([marge_image, padding, ret])
        
        # 画像をモノクロに変換
        marge_image = cv2.cvtColor(marge_image, cv2.COLOR_BGR2GRAY)
        # 二値化
        _, marge_image = cv2.threshold(marge_image, 128, 255, cv2.THRESH_BINARY)
        return marge_image

def make_matrix_image(img):
    matrix_buffer = np.zeros((4*2, 16), dtype=np.uint16)
    
    for x in range(8):
        for y in range(16):
            matrix_buffer[x][y] = 0x0000
            for bit in range(16):
                xindex = x*16 + bit
                yindex = y
                # out of range check
                if xindex >= img.shape[1]:
                    continue
                if yindex >= img.shape[0]:
                    continue
                if img[yindex, xindex] > 127:
                    matrix_buffer[x][y] |= 1 << (15-bit)
    return matrix_buffer

def show_line(console:serial.Serial, cz:CharaZenkaku, text: str):
    img = cz.search_string(text)
    matrix = make_matrix_image(img)
    barray = matrix.tobytes()
    b64 = base64.b64encode(barray) + b'\r\n'
    console.write(b64)

def scroll_line(console:serial.Serial, cz:CharaZenkaku, text: str):
    DEFAULT_SCROLL_WAIT_TIME_SEC = 0.02
    padding_text = "　　　　　　　　　　　"
    target_text = padding_text + text + padding_text
    img = cz.search_string(target_text)

    # 1ループ毎に1列筒削除して左に詰める
    loop_length = img.shape[1]
    for _ in range(loop_length):
        matrix = make_matrix_image(img)
        barray = matrix.tobytes()
        b64 = base64.b64encode(barray) + b'\r\n'
        console.write(b64)
        img = np.delete(img, 0, axis=1)
        time.sleep(DEFAULT_SCROLL_WAIT_TIME_SEC)

if __name__ == "__main__":
    cz = CharaZenkaku()

    com_port = 'COM23'
    baudrate = 921600
    timeout = 1
    
    ser = serial.Serial(com_port, baudrate, timeout=timeout)
    show_line(ser, cz, "ﾊｼﾓﾄﾊTeXｦｵﾎﾞｴﾀ")
    ##scroll_line(ser, cz, "特急電車が通過します。黄色い線の内側でお待ちください。")
    ser.close()
