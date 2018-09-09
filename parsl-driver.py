
import glob
import time
import pathlib

import parsl
from parsl.app.app import bash_app

parsl.set_stream_logger()

# import configuration after setting parsl logging, because interesting
# construction happens during the configuration

import configuration

parsl.load(configuration.parsl_config)


# /-terminated path to work and output base dir
cfg_work_and_out_path = "/projects/LSSTADSP_DESC/benc/"

# singularity image containing the ALCF_1.2i distro
cfg_singularity_img = cfg_work_and_out_path + "ALCF_1.2.simg"

cfg_singularity_url = "shub://benclifford/ALCF_1.2"

# whether to download the singularity image or to
# use the local copy from (eg) a previous run
# probably should be set to True unless testing
# interactively
cfg_singularity_download = False

# set to true to use fake short sleep instead of singularity
cfg_fake = False


cfg_inst_cat_root = "/projects/LSSTADSP_DESC/ALCF_1.2i/inputs/"


# trickle-loop parameters
# submit 10% more jobs than we have nodes for so that there are
# at least some waiting to run
cfg_max_simultaneous_submit = configuration.THETA_NODES * 1.1

cfg_rebalance_seconds = 3 * 60
#cfg_rebalance_seconds = 4 * 60 * 60

cfg_trickle_loop_seconds = 60

@bash_app(executors=['submit-node'])
def cache_singularity_image(local_file, url):
    return "singularity build {} {}".format(local_file, url)


@bash_app(executors=['worker-nodes'])
def run_imsim_in_singularity_fake(nthreads: int, work_and_out_base: str, singularity_img_path: str, inst_cat: str, inst_cat_root: str, stdout=None, stderr=None):
    return "echo start a bash task; sleep 20s ; echo this is stdout ; (echo this is stderr >&2 ) ; false"

@bash_app(executors=['worker-nodes'])
def run_imsim_in_singularity(nthreads: int, work_and_out_base: str, singularity_img_path: str, inst_cat: str, inst_cat_root: str, stdout=None, stderr=None):
    stuff_a = inst_cat.replace(inst_cat_root, "ICROOT", 1)
    stuff_b = stuff_a.replace("/", "_")
    pathbase = "{}/run/{}/".format(work_and_out_base, stuff_b)
    outdir = pathbase + "out/"
    workdir = pathbase + "work/"
    return "echo BENC: info pre singularity; date ; echo BENC id; id ; echo BENC HOME = $HOME; echo BENC hostnaee ; hostname ; echo BENC ls ~ ; ls ~ ; echo BENC launch singularity ; singularity run -B {},{} {} --instcat {} --workdir {} --outdir {} --low_fidelity --subset_size 300 --subset_index 0 --file_id ckpt --processes {}".format(inst_cat_root, work_and_out_base, singularity_img_path, inst_cat, outdir, workdir, nthreads)

def trickle_submit(task_info):

  instance_catalog = task_info
  print("launching a run for instance catalog {}".format(instance_catalog))

  # TODO: factor this base 
  stuff_a = instance_catalog.replace(cfg_inst_cat_root, "ICROOT", 1)
  stuff_b = stuff_a.replace("/", "_")
  pathbase = "{}/run/{}/".format(cfg_work_and_out_path, stuff_b)
  outdir = pathbase + "out/"
  workdir = pathbase + "work/"

  pathlib.Path(workdir).mkdir(parents=True, exist_ok=True) 

  print("app stdout/stderr logging: will create path {}".format(workdir))
  ot = workdir + "task-stdout.txt"
  er = workdir + "task-stderr.txt"
 
  future = run_imsim(63, cfg_work_and_out_path, cfg_singularity_img, instance_catalog, cfg_inst_cat_root, stdout=ot, stderr=er)
  print("launched a run for instance catalog {}".format(instance_catalog))
  return future


print("listing instance catalogs")
# This glob came from Jim Chiang
instance_catalogs = glob.glob('{}/DC2-R1*/0*/instCat/phosim_cat*.txt'.format(cfg_inst_cat_root))
print("there are {} instance catalogs to process".format(len(instance_catalogs)))

print("caching singularity image")


if (not cfg_fake) and cfg_singularity_download:
  singularity_future = cache_singularity_image(cfg_singularity_img, "shub://benclifford/ALCF_1.2i")

  singularity_future.result()

if cfg_fake:
    run_imsim = run_imsim_in_singularity_fake
else:
    run_imsim = run_imsim_in_singularity

print("Starting up trickle-in loop")


todo_tasks = instance_catalogs
submitted_futures = []
last_rebalance = time.time()

while len(todo_tasks) > 0 or len(submitted_futures) > 0:
  balance_ago = time.time() - last_rebalance
  print("trickle loop: looping - {} tasks still to submit, {} futures to wait for, last rebalance was {} ago".format(len(todo_tasks), len(submitted_futures), round(balance_ago) ))

  if balance_ago > cfg_rebalance_seconds:
    print("CALLBACK: rebalance")
    last_rebalance = time.time() # this will be roughly the time the rebalance finished, not cfg_rebalance_seconds after the last rebalance

  # check if any futures are finished, without blocking
  for f in submitted_futures:
    if f.done():
      print("Future f is done")
      print("CALLBACK: task done")
      submitted_futures.remove(f)

  while len(submitted_futures) < cfg_max_simultaneous_submit and len(todo_tasks) > 0:
    print("There is capacity for a new task")
    task_info = todo_tasks.pop()
    f = trickle_submit(task_info)
    submitted_futures.append(f)

  print("trickle loop: end iteration")
  time.sleep(cfg_trickle_loop_seconds)




print("end of parsl-driver")

