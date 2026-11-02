# 3D Builder

Turns a video or a set of photos into a textured 3D model, exported as a `.glb` file and a React Three Fiber component ready for the web.

## How it works

1. **Python pipeline** (`app/pipeline/`): extract frames, estimate camera poses and a sparse point cloud (COLMAP), remove the background, build a dense mesh and texture it (OpenMVS), then generate the web component.
2. **Web app** (`webapp/`, Next.js): a 3D viewer, a page to capture video or photos from a phone, and an upload route that starts the pipeline and reports the job status.
3. **Deploy** (`deploy/oracle/`): provisioning scripts for an ARM64 virtual machine on Oracle Cloud.

A single photo can also give a 2.5D relief of the photographed side, using monocular depth estimation.

## Limits

- The result is one merged mesh, not separate named objects.
- A single photo cannot give the back or sides of an object.

`CONTEXT.md` (in Italian) records the design decisions, the known bugs and the local versus production setup.
