from pathlib import Path
import os,json,io,base64,contextlib,traceback,time,sys
os.environ['MPLBACKEND']='Agg'
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

path=Path(sys.argv[1] if len(sys.argv)>1 else Path(__file__).resolve().parent/'Tour_Navigator_Integrated.ipynb').resolve()
nb=json.loads(path.read_text());os.chdir(path.parent)
outputs=[]
def display(value):
    data={'text/plain':str(value)}
    if hasattr(value,'to_html'):data['text/html']=value.to_html(index=False)
    outputs.append({'output_type':'display_data','data':data,'metadata':{}})
def show(*args,**kwargs):
    buffer=io.BytesIO();plt.gcf().savefig(buffer,format='png',dpi=100,bbox_inches='tight')
    outputs.append({'output_type':'display_data','data':{'image/png':base64.b64encode(buffer.getvalue()).decode(),'text/plain':'<Matplotlib Figure>'},'metadata':{}})
plt.show=show
namespace={'__name__':'__main__','display':display}
number=0;start=time.monotonic()
for idx,cell in enumerate(nb['cells']):
    if cell['cell_type']!='code':continue
    number+=1;outputs=[];stdout=io.StringIO();stderr=io.StringIO();t=time.monotonic()
    try:
        with contextlib.redirect_stdout(stdout),contextlib.redirect_stderr(stderr):
            exec(compile(cell['source'],f'<cell {idx}>','exec'),namespace)
    except Exception:
        print(stdout.getvalue());print(stderr.getvalue());traceback.print_exc();raise
    if stdout.getvalue():outputs.insert(0,{'output_type':'stream','name':'stdout','text':stdout.getvalue()})
    if stderr.getvalue():outputs.append({'output_type':'stream','name':'stderr','text':stderr.getvalue()})
    cell['outputs']=outputs;cell['execution_count']=number
    print(f'Executed code cell {number}: {time.monotonic()-t:.1f}s, {len(outputs)} outputs',flush=True)
    if stdout.getvalue():print(stdout.getvalue()[:1300],flush=True)
    if stderr.getvalue():print('STDERR:',stderr.getvalue()[:1000],flush=True)
nb['metadata']['execution_verification']={'method':'All code cells executed sequentially in one fresh Python process with captured tables and plots; not a socket-backed Jupyter kernel test','python':sys.version.split()[0],'code_cells':number,'elapsed_seconds':round(time.monotonic()-start,2)}
path.write_text(json.dumps(nb,ensure_ascii=False,indent=1),encoding='utf-8')
print('SAVED',path,'seconds',round(time.monotonic()-start,1))
