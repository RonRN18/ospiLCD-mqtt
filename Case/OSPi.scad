/*

    OpenSprinkler Pi (v1.52) with LCD Display Case
    
    Designed by Ron Webb (bigron@gmail.com)
    
    Designed for 20x4 i2c LCD display
    
    May 20, 2024
    Version 0.4
    
*/

use <StudModules.scad>
use <roundedcube.scad>

/*
	Universal variables
*/
$fa     = 1;
$fs     = 0.5; 
bt      = 7;        	// Base Thickness
obx     = 100;			// OSPi Board X Dimmension
oby     = 80;			// OSPi Board Y Dimmension
buf     = 7;	    	// Buffer between case outside for pegs
bc      = 30;       	// Border clearance - How much wider than PCB is case
ph      = 50;       	// Peg Height
asd     = 4.2;      	// Anchor Screw Shaft Diameter
ahd     = 9.1;        	// Anchor Screw Head Diameter
tst     = 2.5;      	// Case side thickness
ttt     = 5;        	// Case surface thickness
crad    = 5;       		// Case rounded radius
drad    = 2.5;      	// LCD Display extrusion radius
dx      = 98;       	// LCD Display extrusion X Dimmension
dy      = 41;     		// LCD Display extrusion Y Dimmension
dty     = 35;       	// LCD Display center offset from vertical top
dbx     = 98;       	// LCD Display Board X Dimmension
dby     = 60;       	// LCD Display Board Y Dimmension
dbso    = 2.5;      	// LCD Display Board Screw Offeset from Edge
m3h     = 5.75;     	// M3 Head clearance diameter
m3d     = 3.1;      	// M3 shaft clearance diameter
m3k     = 3.1;      	// M3 Head Height
cbasex = obx+bc;   		// Base X Dimension
cbasey = oby+bc;    	// Base Y Dimension
pegx = (cbasex/2)-buf;	// Peg X offset from center
pegy = (cbasey/2)-buf;	// Peg Y offset from center 
acin = 15;				// AC In Width
acinh = 15;				// AC In Height		
botw = 90;				// Bottom Ports Width
both = 16.5;			// Bottom Ports Height
ethw = 60;				// Ethernet/USB Width
ethh = 23;				// Ethernet/USB Height
m3l = 10.5;				// M3 Stud length
ohx = (obx/2)-3;		// OSPi Board Screw X offset
ohy = (oby/2)-4;		// OSPi Board Screw y offset



   
Base(0,0,0);   
  
Top(0,0,0); 
 
module Ospi_Board(ox,oy,off=0) {

    difference () {
        translate ([ox-(obx/2),oy-(oby/2),off]) cube([obx,oby,3]);
        translate ([ox-(obx/2)+2,oy-(oby/2)+2,off+3]) cube([obx-4,oby-4,3]);
		}
		m3_long_stud(-ohx,ohy,m3l,0);
        m3_long_stud(-ohx,-ohy,m3l,0);
        m3_long_stud(ohx,ohy,m3l,0);
        m3_long_stud(ohx,-ohy,m3l,0);
    }
    
module Base(Basex,Basey,off=0)  {

    difference () {
        union()  {
			translate ([Basex-(cbasex/2)+1,Basey-(cbasey/2)+1,off]) roundedcube([cbasex-1.5,cbasey-1.5,bt],false,drad,"z");
			translate([-(botw/2),-((cbasey/2)+tst),off]) cube([botw-0.5,tst*2,m3l],false); // Bottom of the Case
			translate([-(cbasex/2)-(tst/2),-33.2, off]) cube([tst*2,acin-0.5,m3l],false); // AC Input
			translate([(cbasex/2)-(tst),-(ethw/2), off] ) cube([tst*2,ethw-0.5,bt],false); // Ethernet/USB Opening
			Ospi_Board(0,0,bt-2);
        }
		union()  {
            translate ([-pegx,0,off]) cylinder(h=(bt*2), d = asd);
            translate ([-pegx,0,(bt/2)]) cylinder(h=(bt*2), d = ahd);            
        }
        union()  {
            translate ([pegx,0,off]) cylinder(h=(bt*2), d = asd);
            translate ([pegx,0,(bt/2)]) cylinder(h=(bt*2), d = ahd);            
        }
		translate([-ohx,ohy,0]) cylinder(h=30, d=m3d);
		translate([-ohx,-ohy,0]) cylinder(h=30, d=m3d);
		translate([ohx,ohy,0]) cylinder(h=30, d=m3d);
		translate([ohx,-ohy,0]) cylinder(h=30, d=m3d);
		translate([-43,-7,bt]) color("Blue") linear_extrude(height = 15, scale = 1) offset(0.01) import("OSPi_8.svg");
    }
        m3_long_stud(-pegx,pegy,ph,off);
        m3_long_stud(-pegx,-pegy,ph,off);
        m3_long_stud(pegx,pegy,ph,off);
        m3_long_stud(pegx,-pegy,ph,off);
    }
    
module Top(Topx,Topy,off=0) {

/*
    Top Variables
*/

    tx  	= obx+bc+(tst*2);   // Top Surface X Dimmension
    ty  	= oby+bc+(tst*2);   // Top Surface Y Dimmension
    tz  	= ph+bt+ttt;        // Top Surface Z Dimmension
    ix  	= tx-(tst*2);       // Top Interior X Dimmension
    iy  	= ty-(tst*2);       // Top Interior Y Dimmension   
    iz  	= tz-ttt;           // Top Interior Z Dimmension
	dbsx	= (dbx/2)-dbso;		// Display Board Screw X Deviation from center
	dbsy	= (dby/2)-dbso;		// Display Board Screw Y Deviation from center
	pegpad	= 8;				// Diameter of Peg Pad



    difference() {
		union() {
			difference() {
				translate([0,0,(tz/2)]) roundedcube([tx,ty,tz], true, crad,"zmax"); // Outer Surface
				translate([0,0,(iz/2)]) roundedcube([ix,iy,iz], true, crad,"zmax"); // Inner Surface
				translate([0,(ty/2)-dty,50]) roundedcube([dx,dy,100], true, drad, "z"); // LCD Display
				translate([-(botw/2),-(ty/2)-(tst*2),0]) cube([botw,20,(both+m3l)],false); // Bottom Ports
				translate([(tx/2)-(tst*2),-ethw/2,off]) cube([20,ethw,(bt+ethh)],false); // RPi USB/Ethernet
				translate([(-(tx/2)-(tst*2)),-33.2,off]) cube([80,acin,(acinh+m3l)],false); // 24 VAC in
			}
			translate([0,(ty/2)-dty,tz-5]) rotate([0,180,0]) m3_long_stud(-dbsx,dbsy,1);
			translate([0,(ty/2)-dty,tz-5]) rotate([0,180,0]) m3_long_stud(-dbsx,-dbsy,1);
			translate([0,(ty/2)-dty,tz-5]) rotate([0,180,0]) m3_long_stud(dbsx,dbsy,1);
			translate([0,(ty/2)-dty,tz-5]) rotate([0,180,0]) m3_long_stud(dbsx,-dbsy,1);
			translate([-pegx,pegy,tz]) rotate([0,180,0]) cylinder(h=12.135,d=pegpad);
			translate([-pegx,-pegy,tz]) rotate([0,180,0]) cylinder(h=12.135,d=pegpad);
			translate([pegx,pegy,tz]) rotate([0,180,0]) cylinder(h=12.135,d=pegpad);
			translate([pegx,-pegy,tz]) rotate([0,180,0]) cylinder(h=12.135,d=pegpad);
		} 
		translate([-pegx,pegy,tz]) rotate([0,180,0]) cylinder(h=m3k,d=m3h);
		translate([-pegx,-pegy,tz]) rotate([0,180,0]) cylinder(h=m3k,d=m3h);
		translate([pegx,pegy,tz]) rotate([0,180,0]) cylinder(h=m3k,d=m3h);
		translate([pegx,-pegy,tz]) rotate([0,180,0]) cylinder(h=m3k,d=m3h);
		translate([-pegx,pegy,tz]) rotate([0,180,0]) cylinder(h=50,d=m3d);
		translate([-pegx,-pegy,tz]) rotate([0,180,0]) cylinder(h=50,d=m3d);
		translate([pegx,pegy,tz]) rotate([0,180,0]) cylinder(h=50,d=m3d);
		translate([pegx,-pegy,tz]) rotate([0,180,0]) cylinder(h=50,d=m3d);
		translate([-54,-30,(tz-2)]) color("Blue") linear_extrude(height = 2, center = false, convexity = 10)offset(0.01) import("OSPi.svg");
}		
}   
