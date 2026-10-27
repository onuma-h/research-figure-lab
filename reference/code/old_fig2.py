"""CasaXPS ASCII TXT -> two depth-stacked plots (raw CPS and normalized), PNG/PDF.
No smoothing/interpolation; source data remain untouched.
"""
from pathlib import Path
from io import StringIO
import re
import warnings
import unicodedata
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.ticker import AutoMinorLocator
from matplotlib.transforms import blended_transform_factory

# ===== User settings =====
DATA_DIR = Path.home() / 'Desktop' / 'graph' / 'XPS'
OUTPUT_DIR = DATA_DIR
SELECT_FILES = None  # None: all .txt; or list of filenames

# 各自の環境に合わせて設定（測定する元素の領域とピーク中心 [eV]。以下は一般的なサンプル値）
PEAK_CENTERS = {
    'C 1s':[284.8], 'O 1s':[531.0], 'Au 4f':[84.0,87.7],
}
PEAK_MARGIN_EV = 5.0
MANUAL_XRANGES = {}  # example: {'C 1s': (295,280)}

PLOT_COMPONENTS = True
PLOT_ENVELOPE = True
PLOT_BACKGROUND = False
RAW_OFFSET_MULTIPLIER = 1.30  # same rule as previous non-normalized plot
FIXED_RAW_Y_SHIFT_CPS = None  # specify numeric override if needed
NORMALIZED_Y_SHIFT = 1.30     # same as previous normalized plot
VERTICAL_PAD_FRACTION = 0.012  # reduced blank area above/below; 1.2% of plotted range
FIGSIZE = (6.8, 6.7)
DPI = 600
COLORS = ['#222222','#d62728','#1766b3','#2c8d57','#8a42ae','#bd741a']

plt.rcParams.update({
    'font.family':'DejaVu Sans', 'font.size':12,
    'axes.linewidth':1.0, 'axes.grid':False,
    'xtick.direction':'in', 'ytick.direction':'in',
    'pdf.fonttype':42, 'ps.fonttype':42
})


def read_casa_txt(path):
    lines = path.read_text(encoding='utf-8-sig', errors='replace').splitlines()
    header_idx = next((i for i,line in enumerate(lines)
        if line.startswith('K.E.\t') and 'B.E.' in line.split('\t') and 'CPS' in line.split('\t')),None)
    if header_idx is None:
        raise ValueError(f'{path.name}: CasaXPS K.E./B.E./CPS header not found')
    df = pd.read_csv(StringIO('\n'.join(lines[header_idx:])), sep='\t', engine='python')
    col = df.columns.tolist()
    be_idx = col.index('B.E.')
    cps_idx = col.index('CPS',be_idx)
    fit_idx = next((i for i in range(cps_idx+1,len(col)) if col[i]=='Envelope CPS'),None)
    bg_idx = next((i for i in range(cps_idx+1,len(col)) if col[i]=='Background CPS'),None)
    limit = min([i for i in (bg_idx,fit_idx) if i is not None],default=len(col))
    components = [i for i in range(cps_idx+1,limit)
                  if not str(col[i]).lower().startswith('unnamed')]
    idxs = [be_idx,cps_idx] + components
    if bg_idx is not None: idxs.append(bg_idx)
    if fit_idx is not None: idxs.append(fit_idx)
    numeric = df.iloc[:,idxs].apply(pd.to_numeric,errors='coerce')
    mask = np.isfinite(numeric.iloc[:,0]) & np.isfinite(numeric.iloc[:,1])
    if not mask.all():
        warnings.warn(f'{path.name}: skipped {int((~mask).sum())} invalid BE/CPS rows')
    order = np.argsort(-numeric.loc[mask].iloc[:,0].to_numpy())
    def values(index):
        if index is None: return None
        return pd.to_numeric(df.iloc[:,index],errors='coerce').loc[mask].iloc[order].to_numpy(float)
    first = lines[0] if lines else ''
    region_match = re.search(r'([A-Z][a-z]?)\s*(\d+[spdf])',first,re.I)
    region = f'{region_match.group(1).capitalize()} {region_match.group(2).lower()}' if region_match else 'XPS'
    # ファイル名中の「sampleA_１」「表面１」などを同一試料として認識する
    normalized_name = unicodedata.normalize('NFKC', path.stem)
    file_match = re.match(
        r'^(?P<sample>.+?)_(?P<depth>表面|surface|\d+(?:\.\d+)?)'
        r'(?P<variant>.*?)_(?P<element>[A-Za-z]+)_(?P<orbital>\d+[spdf])#',
        normalized_name, re.I
    )
    cycle = re.search(r'Cycle\s+(\d+)', first, re.I)
    if file_match:
        sample = file_match.group('sample').lower()
        variant = file_match.group('variant').strip('_ -')
        depth = file_match.group('depth')
        # 同一試料の識別番号のみ残す（例: sampleA_１ → sampleA_1 / 表面１ → 表面1）
        sample_id = f'{sample}_{variant}' if variant else sample
        group = f'{sample_id}_{region.replace(" ", "_")}'
    else:
        # 想定外の命名でもCycle値から深さを取得
        depth = cycle.group(1) if cycle else 'unknown'
        sample = normalized_name.split('_')[0].lower()
        group = f'{sample}_{region.replace(" ", "_")}'
        warnings.warn(f'{path.name}: 命名規則が不明のため先頭部分で試料を分類')
    # ファイル名とCasaXPS内部のCycleが異なるときは安全のため停止
    if cycle:
        inferred = 0 if depth.lower() in ('表面', 'surface') else float(depth) if re.fullmatch(r'\d+(?:\.\d+)?',depth) else None
        if inferred is not None and float(cycle.group(1)) != float(inferred):
            raise ValueError(f'{path.name}: ファイル名深さとCycle番号が一致しません')
    depth_num = 0.0 if depth.lower() in ('表面','surface') else (
        float(depth) if re.fullmatch(r'\d+(?:\.\d+)?',depth) else float('inf'))
    label = ('Etch 0 s' if depth_num==0 else f'Etch {depth_num:g} s'
             if np.isfinite(depth_num) else str(depth))
    return dict(path=path,region=region,group=group,depth_num=depth_num,
                label=label,x=values(be_idx),raw=values(cps_idx),
                components=[values(i) for i in components],fit=values(fit_idx),bg=values(bg_idx))


def plot_group(records, normalized, output_dir):
    records = sorted(records,key=lambda r:(r['depth_num'],r['path'].name))
    if len({r['region'] for r in records})!=1:
        raise ValueError('Multiple XPS regions in one group')
    region = records[0]['region']
    all_x = np.concatenate([r['x'] for r in records])
    lo,hi = float(np.min(all_x)),float(np.max(all_x))
    if region in MANUAL_XRANGES:
        lo,hi = sorted(MANUAL_XRANGES[region])
    elif region in PEAK_CENTERS:
        lo = min(PEAK_CENTERS[region])-PEAK_MARGIN_EV
        hi = max(PEAK_CENTERS[region])+PEAK_MARGIN_EV
    # Restrict to actual measured BE range (no extrapolation)
    lo,hi = max(lo,float(np.min(all_x))),min(hi,float(np.max(all_x)))
    if lo>=hi: raise ValueError(f'{region}: Invalid binding-energy range')
    prepared=[]
    for r in records:
        mask = np.isfinite(r['x']) & (r['x']>=lo) & (r['x']<=hi)
        if not np.any(mask): raise ValueError(f"{r['path'].name}: no data in displayed range")
        maximum=float(np.nanmax(r['raw'][mask]))
        if normalized and (not np.isfinite(maximum) or maximum<=0):
            raise ValueError(f"{r['label']}: invalid raw CPS maximum")
        prepared.append((r,mask,maximum if normalized else 1.0))
    raw_values=np.concatenate([r['raw'][m] for r,m,_ in prepared])
    span=float(np.nanmax(raw_values)-np.nanmin(raw_values))
    shift = (float(NORMALIZED_Y_SHIFT) if normalized else
             float(FIXED_RAW_Y_SHIFT_CPS) if FIXED_RAW_Y_SHIFT_CPS is not None
             else max(span*RAW_OFFSET_MULTIPLIER,1.0))
    if shift<=0: raise ValueError('Y shift must be positive')

    fig,ax=plt.subplots(figsize=FIGSIZE)
    min_y,max_y=np.inf,-np.inf
    for i,(r,mask,divisor) in enumerate(prepared):
        x=r['x'][mask]
        offset=(len(records)-i-1)*shift
        color=COLORS[i%len(COLORS)]
        def draw(ydata,linewidth,alpha,zorder,linestyle='-'):
            nonlocal min_y,max_y
            if ydata is None: return
            y=ydata[mask]/divisor+offset
            valid=np.isfinite(x)&np.isfinite(y)
            if not valid.any():return
            ax.plot(x[valid],y[valid],color=color,lw=linewidth,
                    alpha=alpha,zorder=zorder,ls=linestyle)
            min_y=min(min_y,float(np.min(y[valid])))
            max_y=max(max_y,float(np.max(y[valid])))
        if PLOT_COMPONENTS:
            for component in r['components']:
                draw(component,0.65,0.25,1)
        if PLOT_BACKGROUND: draw(r['bg'],0.65,0.25,1,'--')
        if PLOT_ENVELOPE: draw(r['fit'],0.90,0.45,2)
        draw(r['raw'],1.50,1.0,4)
        raw_y=r['raw'][mask]/divisor+offset
        label_y=float(np.nanmin(raw_y)+0.83*np.ptp(raw_y))
        ax.text(0.025,label_y,r['label'],color=color,fontsize=10,
                transform=blended_transform_factory(ax.transAxes,ax.transData),
                ha='left',va='center',clip_on=True)
    ax.set_xlim(hi,lo)  # higher BE on left
    extent=max_y-min_y
    padding = max(extent*VERTICAL_PAD_FRACTION,1e-6)
    ax.set_ylim(min_y-padding,max_y+padding)
    ax.set_xlabel('Binding Energy [eV]',fontsize=13)
    ax.set_ylabel('Normalized Intensity [a.u.]' if normalized else 'Intensity [CPS]',fontsize=13)
    ax.set_yticks([])  # offset-stack: suppress potentially misleading absolute ticks
    ax.xaxis.set_minor_locator(AutoMinorLocator())
    ax.tick_params(axis='both',which='both',direction='in')
    ax.grid(False)
    fig.subplots_adjust(left=.16,right=.97,bottom=.11,top=.99)
    safe=re.sub(r'[^A-Za-z0-9_-]+','_',records[0]['group'])
    suffix='normalized' if normalized else 'raw_CPS'
    output_dir.mkdir(parents=True,exist_ok=True)
    png=output_dir/f'{safe}_Depth_{suffix}.png'
    pdf=output_dir/f'{safe}_Depth_{suffix}.pdf'
    fig.savefig(png,dpi=DPI,bbox_inches='tight',pad_inches=.02)
    fig.savefig(pdf,bbox_inches='tight',pad_inches=.02)
    plt.show()
    plt.close(fig)
    print(f"{'Normalized' if normalized else 'Raw'}: Y shift={shift:.4f} {'a.u.' if normalized else 'CPS'}")
    print('Saved:',png,'and',pdf)
    return png,pdf


def main():
    if not DATA_DIR.exists(): raise FileNotFoundError(DATA_DIR)
    paths=[DATA_DIR/name for name in SELECT_FILES] if SELECT_FILES is not None else sorted(DATA_DIR.glob('*.txt'))
    if not paths: raise FileNotFoundError(f'No .txt files in {DATA_DIR}')
    groups={}
    for path in paths:
        if not path.is_file():
            warnings.warn(f'Not found: {path}')
            continue
        try:
            r=read_casa_txt(path)
            groups.setdefault(r['group'],[]).append(r)
        except Exception as exc:
            warnings.warn(f'Skipped {path.name}: {exc}')
    if not groups: raise ValueError('No valid CasaXPS files found')
    for name,records in groups.items():
        print('\nGroup:',name,'| depth count:',len(records))
        for r in records:
            print(r['label'],f"components={len(r['components'])}")
        plot_group(records,False,OUTPUT_DIR)
        plot_group(records,True,OUTPUT_DIR)

if __name__=='__main__':
    main()
