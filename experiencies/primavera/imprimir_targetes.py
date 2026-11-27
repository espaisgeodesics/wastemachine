"""Print-ready A4 ArUco cards from the verified DICT_4X4_50 bit patterns."""
import json,sys
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont

NAMES=['Violí solista','Flauta','Oboè','Viola','Violoncel','Alba · ambient Mi','Brots · arpegi Mi major']

def create(folder):
    folder=Path(folder);folder.mkdir(parents=True,exist_ok=True)
    bits=json.loads(Path(__file__).with_name('marker_bits.json').read_text())
    try:
        title=ImageFont.truetype('DejaVuSans.ttf',40);small=ImageFont.truetype('DejaVuSans.ttf',27)
    except OSError:title=small=ImageFont.load_default(size=30)
    pages=[]
    for page in range(2):
        sheet=Image.new('RGB',(2480,3508),'white');draw=ImageDraw.Draw(sheet)
        for slot in range(6):
            i=page*6+slot
            if i>=7:break
            col,row=slot%2,slot//2;left=160+col*1160;top=140+row*1080
            draw.rectangle((left,top,left+1000,top+1000),outline='#b0b0b0',width=2)
            draw.text((left+500,top+65),f'TARGETA {i+1:02d}',font=title,fill='black',anchor='mm')
            draw.text((left+500,top+120),NAMES[i],font=small,fill='black',anchor='mm')
            code=Image.new('L',(6,6),255)
            code.putdata([0 if x=='1' else 255 for line in bits[i] for x in line])
            code=code.resize((660,660),Image.Resampling.NEAREST).convert('RGB')
            sheet.paste(code,(left+170,top+210))
            draw.text((left+500,top+930),f'ATMO · ID {i} · DICT_4X4_50',font=small,fill='black',anchor='mm')
            quiet=Image.new('RGB',(900,900),'white');quiet.paste(code,(120,120))
            quiet.save(folder/f'TARGETA_{i+1:02d}_ID_{i}.png')
        pages.append(sheet)
    pages[0].save(folder/'TARGETES_01_A_07.pdf','PDF',resolution=300,save_all=True,append_images=pages[1:])

if __name__=='__main__':create(Path(sys.argv[1]))
