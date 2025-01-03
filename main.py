# chara_zenkaku.txt から入力された文字の
# 行数と何文字目かを取得する

import cv2
import numpy as np
import serial
import time
import base64
import cv2

DEFAULT_SCROLL_WAIT_TIME_SEC = 0.02

def search_text(chara):
    found = (-1, -1)
    with open('chara_zenkaku.txt', mode='r', encoding="utf-8") as f:
        lines = f.readlines()
        for i, line in enumerate(lines):
            if chara in line:
                found = (i, line.index(chara))
                break
    return found

def search_img(line, num):
    x_offset = 50
    y_offset = 50
    x_step = 17
    y_step = 17
    x_size = 16
    y_size = 16

    img = cv2.imread('chara_zenkaku.png')
    x = x_offset + num * x_step
    y = y_offset + line * y_step
    img = img[y:y+y_size, x:x+x_size]

    return img

def search_string(string:str):
    marge_image = []
    for chara in string:
        ret = search_text(chara)
        if ret == (-1, -1):
            continue
        ret = search_img(ret[0], ret[1])
        # 画像を結合し左詰めにする
        if len(marge_image) == 0:
            marge_image = ret
        else:
            padding = cv2.imread('padding.bmp')
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

def scroll_line(console:serial.Serial, text: str):
    padding_text = "　　　　　　　　　　　"
    target_text = padding_text + text + padding_text
    img = search_string(target_text)

    # 1ループ毎に1列筒削除して左に詰める
    loop_length = img.shape[1]
    for _ in range(loop_length):
        matrix = make_matrix_image(img)
        barray = matrix.tobytes()
        b64 = base64.b64encode(barray) + b'\r\n'
        ser.write(b64)
        img = np.delete(img, 0, axis=1)
        time.sleep(DEFAULT_SCROLL_WAIT_TIME_SEC)
    
if __name__ == '__main__':
    com_port = 'COM8'
    baudrate = 921600
    timeout = 1

    ser = serial.Serial(com_port, baudrate, timeout=timeout)
    scroll_line(ser, "こんにちは")
    ser.close()