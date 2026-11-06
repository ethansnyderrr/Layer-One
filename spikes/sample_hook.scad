// Hand-written sample for testing the pipeline without Claude:
//   python spikes/generate_spike.py --scad spikes/sample_hook.scad
width = 20;       // hook width (mm)
thickness = 4;    // plate thickness (mm)
height = 50;      // back plate height (mm)
hook_depth = 25;  // how far the hook sticks out (mm)
lip = 15;         // height of the front lip (mm)
screw_d = 5;      // screw hole diameter (mm)
$fn = 64;

difference() {
  union() {
    cube([width, thickness, height]);                                  // back plate
    cube([width, hook_depth, thickness]);                              // bottom arm
    translate([0, hook_depth - thickness, 0]) cube([width, thickness, lip]);  // front lip
  }
  translate([width / 2, -1, height - 10]) rotate([-90, 0, 0])
    cylinder(d = screw_d, h = thickness + 2);                          // screw hole
}
