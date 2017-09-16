#!BPY
# vim: set sts=0 noet :

bl_info = {
	"name": "THPS PSX model/trigger tools",
	"description": "Tools for the Tony Hawk's Pro Skater PS1 engine model and trigger files.",
	"author": "GreaseMonkey",
	"version": (0, 0, 0,),
	"blender": (2, 78, 0,),
	"location": "File > Import-Export > THPS map (*.trg)",
	"category": "Import-Export",
}

import math
import random
import struct

import bpy

#
# Helpers
#

def pad16(fp):
	skipme = (0x2-fp.tell())&0x1
	if skipme != 0:
		fp.write(b"\x00"*skipme)

def pad32(fp):
	skipme = (0x4-fp.tell())&0x3
	if skipme != 0:
		fp.write(b"\x00"*skipme)

def rgb15(r,g,b):
	r >>= 3
	g >>= 3
	b >>= 3
	if r == 0 and g == 0 and b == 0: b = 1
	v = (b<<10)|(g<<5)|(r)#|0x8000
	return v

#
# TRG pickup types
#

SPickup = 5
KPickup = 4
APickup = 6
TPickup = 15
EPickup = 10
TapePickup = 16
MoneyPickup250 = 24
#MoneyPickup20 = 24
MoneyPickup50 = 25
MoneyPickup100 = 26
LevelPickup = 33

#
# TRG commands
#

def SetCheatRestarts(*restarts):
	return ((2, ""+("s"*len(restarts))+"s",)
		+ tuple(map(str, restarts))
		+ ("",))
def SendPulse(): return (3, "",)
def SendActivate(): return (4, "",)
def SendSuspend(): return (5, "",)

def SendSignal(): return (10, "",)
def SendKill(): return (11, "",)
def SendKillLoudly(): return (12, "",)
def SendVisible(a): return (13, "h", a,)

def SetFoggingParams(a,b,c): return (104, "HHH", a,b,c,)

def Text(s): return (115, "s", s,)

def SpoolIn(name): return (126, "s", name,)
def SpoolOut(name): return (127, "s", name,)
def SpoolEnv(name): return (128, "s", name,)

def SetInitialPulses(a): return (134, "h", a,)

def SetRestart(name): return (140, "s", name,)

def SetObjFile(name): return (142, "s", name,)
def SetGameLevel(a): return (147, "H", a,)

def KillBruce(): return (152, "", )

def SetReverbType(typ): return (157, "H", typ,)
def EndLevel(): return (158, "", )

def SetOTPushback(a): return (166, "H", a,)
def SetOTPushback2(a): return (169, "H", a,)

def SetRestart2(name): return (178, "s", name,)

def SetSkyColor(a,b): return (202, "HH", a,b,)
def SetFadeColor(a,b): return (200, "HH", a,b,)

def EndCommandList(): return (65535, "",)

#
# TRG class
#

class TRG(object):
	class TRGNode(object):
		def __init__(self, *, idx, typ):
			self.idx = idx
			self.typ = typ
			self.links = []

		def add_link(self, *, other):
			if other not in self.links:
				self.links.append(other)

		def write_links(self, *, fp):
			fp.write(struct.pack("<H", len(self.links)))
			for link in self.links:
				fp.write(struct.pack("<H", link.idx))

		def write(self, *, fp):
			fp.write(struct.pack("<H", self.typ))

	class TRGNodeWithOps(TRGNode):
		def __init__(self, *, idx, typ, ops):
			super(TRG.TRGNodeWithOps, self).__init__(idx=idx, typ=typ)
			self.ops = list(ops)

		def write_ops(self, *, fp):
			for (opc, fields, *args,) in self.ops:
				fp.write(struct.pack("<H", opc))
				#print(fields, args)

				for (fsym, fval,) in zip(fields, args):
					#print(fsym, repr(fval))
					if fsym in ("h","H",):
						fp.write(struct.pack("<"+fsym, fval))
					elif fsym in ("s",):
						pad16(fp)
						fp.write(fval.encode("utf-8") + b"\x00")
						pad16(fp)
					else:
						#print(fsym, fval)
						assert False

	class AutoExecNode(TRGNodeWithOps):
		def __init__(self, *, idx, ops):
			super(TRG.AutoExecNode, self).__init__(idx=idx, typ=4, ops=ops)

		def write(self, *, fp):
			super(TRG.AutoExecNode, self).write(fp=fp)
			self.write_ops(fp=fp)

	class PowrupNode(TRGNodeWithOps):
		def __init__(self, *, idx, powrup, px,py,pz, unk1=0x00010000, ops):
			super(TRG.PowrupNode, self).__init__(idx=idx, typ=5, ops=ops)
			self.powrup = powrup
			self.px = px
			self.py = py
			self.pz = pz
			self.unk1 = unk1

		def write(self, *, fp):
			super(TRG.PowrupNode, self).write(fp=fp)
			fp.write(struct.pack("<H", self.powrup))
			self.write_links(fp=fp)
			pad32(fp)
			fp.write(struct.pack("<iii", self.px, self.py, self.pz))
			fp.write(struct.pack("<I", self.unk1))
			pad16(fp)
			self.write_ops(fp=fp)

	class CommandPointNode(TRGNodeWithOps):
		def __init__(self, *, idx, name, ops):
			super(TRG.CommandPointNode, self).__init__(idx=idx, typ=6, ops=ops)
			self.name = name

		def write(self, *, fp):
			super(TRG.CommandPointNode, self).write(fp=fp)
			self.write_links(fp=fp)
			pad32(fp)
			fp.write(struct.pack("<I", self.name))
			self.write_ops(fp=fp)


	class RestartNode(TRGNodeWithOps):
		def __init__(self, *, idx, px,py,pz, sx,sy,sz, name, ops):
			super(TRG.RestartNode, self).__init__(idx=idx, typ=8, ops=ops)
			self.px = px
			self.py = py
			self.pz = pz
			self.sx = sx
			self.sy = sy
			self.sz = sz
			self.name = name

		def write(self, *, fp):
			super(TRG.RestartNode, self).write(fp=fp)
			self.write_links(fp=fp)
			pad32(fp)
			fp.write(struct.pack("<iii", self.px, self.py, self.pz))
			fp.write(struct.pack("<hhh", self.sx, self.sy, self.sz))
			fp.write(self.name.encode("utf-8")+b"\x00")
			pad16(fp)
			self.write_ops(fp=fp)

	class RailPointNode(TRGNode):
		def __init__(self, *, idx, px,py,pz, unk1):
			super(TRG.RailPointNode, self).__init__(idx=idx, typ=10)
			self.px = px
			self.py = py
			self.pz = pz
			self.unk1 = unk1

		def write(self, *, fp):
			super(TRG.RailPointNode, self).write(fp=fp)
			self.write_links(fp=fp)
			pad32(fp)
			fp.write(struct.pack("<iii", self.px, self.py, self.pz))
			fp.write(struct.pack("<h", self.unk1))

	def __init__(self):
		self.chunks = []

	def new_autoexec(self, *, ops):
		idx = len(self.chunks)
		node = TRG.AutoExecNode(
			idx=idx,
			ops=ops)
		self.chunks.append(node)
		return node

	def new_powrup(self, *, powrup, px,py,pz, unk1=0x00010000, ops):
		idx = len(self.chunks)
		node = TRG.PowrupNode(
			idx=idx,
			powrup=powrup,
			px=px, py=py, pz=pz,
			unk1=unk1,
			ops=ops)
		self.chunks.append(node)
		return node

	def new_commandpoint(self, *, name=0x00000000, ops):
		idx = len(self.chunks)
		node = TRG.CommandPointNode(
			idx=idx,
			name=name,
			ops=ops)
		self.chunks.append(node)
		return node

	def new_restart(self, *, px,py,pz, sx,sy,sz, name, ops):
		idx = len(self.chunks)
		node = TRG.RestartNode(
			idx=idx,
			px=px, py=py, pz=pz,
			sx=sx, sy=sy, sz=sz,
			name=name,
			ops=ops)
		self.chunks.append(node)
		return node

	def new_railpoint(self, *, px,py,pz, unk1=16):
		idx = len(self.chunks)
		node = TRG.RailPointNode(
			idx=idx,
			px=px, py=py, pz=pz,
			unk1=unk1)
		self.chunks.append(node)
		return node

	def write(self, *, fname):
		fp = open(fname, "wb")

		# Header
		fp.write(b"_TRG\x02\x00\x00\x00")
		fp.write(struct.pack("<I",len(self.chunks)))

		# Chunk pointer table prefill
		chunk_ptrtab_pos = fp.tell()
		chunk_ptrtab = []
		fp.write(b"\x00"*4*len(self.chunks))

		# Chunks
		for chunk in self.chunks:
			chunk_ptrtab.append(fp.tell())
			chunk.write(fp=fp)
			pad16(fp)

		# Chunk pointer table postfill
		ptr_tmp0 = fp.tell()
		fp.seek(chunk_ptrtab_pos)
		for ptr in chunk_ptrtab:
			fp.write(struct.pack("<I", ptr))
		fp.seek(ptr_tmp0)

		# Done
		fp.close()

#
# PSX class
#

class PSX(object):
	class PObject(object):
		def __init__(self, *, idx, flags1=0, px,py,pz, model_idx,tx=0,ty=0):
			self.idx = idx
			self.flags1 = flags1
			self.px = px
			self.py = py
			self.pz = pz
			self.model_idx = model_idx
			self.tx = tx
			self.ty = ty

		def write(self, *, fp):
			fp.write(struct.pack("<IiiiIHHhhII"
				, self.flags1
				, self.px
				, self.py
				, self.pz
				, 0
				, 0
				, self.model_idx
				, self.tx
				, self.ty
				, 0
				, 0 #self.ptr_paldata
				))
			self.ptr_paldata_ptr = fp.tell() - 4

	class PModel(object):
		class PFace(object):
			def __init__(self, *, idx, rflags, vidxs, cmd, sflags, tidx=0, tpoints=[]):
				self.idx = idx
				self.rflags = rflags
				self.vidxs = list(vidxs)
				self.cmd = list(cmd)
				self.sflags = sflags
				self.tidx = tidx
				self.tpoints = list(tpoints)

		def __init__(self, *, idx, unk1=8, gunkl2=0xFFFF7FFF):
			self.unk1 = unk1

			self.vertices = []
			self.faces = []

			self.gunkl2 = gunkl2

		def vertex(self, x,y,z):
			idx = len(self.vertices)
			p = (x,y,z,0,)
			self.vertices.append(p)
			return idx

		def face(self, *, rflags, vidxs, cmd, sflags, tidx=0, tpoints=[]):
			idx = len(self.faces)
			self.faces.append(PSX.PModel.PFace(
				idx=idx,
				rflags=rflags,
				vidxs=vidxs,
				cmd=cmd,
				sflags=sflags,
				tidx=tidx,
				tpoints=tpoints))

			return idx

		def write(self, *, fp):
			fp.write(struct.pack("<H", self.unk1))
			fp.write(struct.pack("<H", len(self.vertices)))
			fp.write(struct.pack("<H", len(self.faces))) # planes!
			fp.write(struct.pack("<H", len(self.faces)))

			self.radius = max(*map(
				lambda x: int(math.ceil(math.sqrt(
					(x[0]**2+x[1]**2+x[2]**2)<<24
				)))&~0xFFF,
				self.vertices))
			fp.write(struct.pack("<I", self.radius))
			self.xmin = min(*map(lambda x: x[0], self.vertices))
			self.xmax = max(*map(lambda x: x[0], self.vertices))
			self.ymin = min(*map(lambda x: x[1], self.vertices))
			self.ymax = max(*map(lambda x: x[1], self.vertices))
			self.zmin = min(*map(lambda x: x[2], self.vertices))
			self.zmax = max(*map(lambda x: x[2], self.vertices))
			fp.write(struct.pack("<hh", self.xmax, self.xmin))
			fp.write(struct.pack("<hh", self.ymax, self.ymin))
			fp.write(struct.pack("<hh", self.zmax, self.zmin))
			fp.write(struct.pack("<I", self.gunkl2))

			for vtx in self.vertices:
				fp.write(struct.pack("<hhhh", *vtx))

			# Planes
			for face in self.faces:
				v0 = self.vertices[face.vidxs[0]]
				v1 = self.vertices[face.vidxs[1]]
				v2 = self.vertices[face.vidxs[2]]
				x0,y0,z0,_, = v0
				x1,y1,z1,_, = v1
				x2,y2,z2,_, = v2
				dx1,dy1,dz1 = x1-x0,y1-y0,z1-z0
				dx2,dy2,dz2 = x2-x0,y2-y0,z2-z0
				fx = float((dy2*dz1)-(dz2*dy1))
				fy = float((dz2*dx1)-(dx2*dz1))
				fz = float((dx2*dy1)-(dy2*dx1))
				fx /= 4096.0
				fy /= 4096.0
				fz /= 4096.0
				norm = 1.0/max((fx*fx+fy*fy+fz*fz)**0.5, 0.0001)
				# BOUNCY SHIT
				#norm *= (1.0/0.84 if (face_data[j]["f_surf_flags"] & 0x0100) == 0 else 1.0*0.84)
				fx *= norm
				fy *= norm
				fz *= norm
				x = int(round(fx*4096))
				y = int(round(fy*4096))
				z = int(round(fz*4096))
				fp.write(struct.pack("<hhhh", x, y, z, 0))

			# Actually the faces this time
			for face in self.faces:
				is_gouraud = ((face.rflags & 0x0800) != 0)
				is_textured = ((face.rflags & 0x0003) != 0)
				is_triangle = ((face.rflags & 0x0010) != 0)
				length = (0x001C if is_textured else 0x0010)
				fp.write(struct.pack("<HH", face.rflags, length))
				fp.write(struct.pack("<BBBB", *face.vidxs))
				fp.write(struct.pack("<BBBB", *face.cmd))
				fp.write(struct.pack("<HH", face.idx, face.sflags))
				if is_textured:
					fp.write(struct.pack("<I", face.tidx))
					for i in range(4):
						fp.write(struct.pack("<BB", *face.tpoints[i]))

	class PTexture(object):
		def __init__(self, *, idx, name, iw, ih, unk1=0x0000, bpp, pal, data):
			self.idx = idx
			self.name = name
			self.bpp = bpp
			self.iw = iw
			self.ih = ih
			self.unk1 = unk1
			assert (iw&0x7) == 0
			assert (ih&0x7) == 0
			if self.bpp not in (4, 8,):
				raise Exception("bpp invalid: %s" % (repr(self.bpp),))
			self.pal = list(pal)
			if len(self.pal) != (1<<self.bpp):
				raise Exception("palette size invalid for bpp")
			self.data = list(data)

		def write_palette_4bpp(self, *, fp):
			if self.bpp != 4:
				raise Exception("bpp must be 4 for this function")

			fp.write(struct.pack("<I", self.name))
			for i in range(16):
				fp.write(struct.pack("<H", self.pal[i]))

		def write_palette_8bpp(self, *, fp):
			if self.bpp != 8:
				raise Exception("bpp must be 8 for this function")

			fp.write(struct.pack("<I", self.name))
			for i in range(256):
				fp.write(struct.pack("<H", self.pal[i]))

		def write_data(self, *, fp):
			#t_unk1, t_palsize, t_namehash, t_texidx, t_width, t_height, = struct.unpack("<IIIIHH", fp.read(20))
			fp.write(struct.pack("<IIIIHH"
				, self.unk1
				, 1<<self.bpp
				, self.name
				, self.idx
				, self.iw
				, self.ih))
			fp.write(bytes(self.data))
			pad32(fp)

	def __init__(self):
		self.objs = []
		self.mdls = []
		self.texs = []
		self.palents = [[random.randint(0,255) for i in range(3)]+[0] for j in range(256)]

	def texture(self, *, iw, ih, unk1=0x0000, bpp, pal, data):
		idx = len(self.texs)
		tex = PSX.PTexture(
			idx=idx,
			name=0xFEED0000+idx,
			iw=iw,
			ih=ih,
			unk1=unk1,
			bpp=bpp,
			pal=pal,
			data=data)

		self.texs.append(tex)

		return tex.idx, tex.name

	def thing(self, *, flags1=0, px,py,pz, tx=0,ty=0, unk1=8, gunkl2=0xFFFF7FFF):
		idx = len(self.objs)
		assert idx == len(self.mdls)
		obj = PSX.PObject(
			idx=idx,
			flags1=flags1,
			px=px,
			py=py,
			pz=pz,
			model_idx=idx,
			tx=tx,
			ty=ty)
		mdl = PSX.PModel(
			idx=idx,
			unk1=unk1,
			gunkl2=gunkl2)
		self.objs.append(obj)
		self.mdls.append(mdl)
		return mdl

	def write(self, *, fname):
		fp = open(fname, "wb")

		# Header
		fp.write(b"\x04\x00\x02\x00")
		metaptr_ptr = fp.tell() # how meta
		fp.write(struct.pack("<I", 0))

		# Objects
		palptrs = []
		fp.write(struct.pack("<I", len(self.objs)))
		for obj in self.objs:
			obj.write(fp=fp)
			palptrs.append(obj.ptr_paldata_ptr)

		# Models
		mdlptrs = []
		fp.write(struct.pack("<I", len(self.mdls)))
		mdlptrs_ptr = fp.tell()
		for mdl in self.mdls:
			fp.write(struct.pack("<I", 0))
		for mdl in self.mdls:
			pad32(fp)
			mdlptrs.append(fp.tell())
			mdl.write(fp=fp)
		pad32(fp)
		tmp = fp.tell()
		fp.seek(mdlptrs_ptr)
		for p in mdlptrs:
			fp.write(struct.pack("<I", p))
		fp.seek(tmp)

		# Palette
		tmp = fp.tell()
		fp.seek(metaptr_ptr)
		fp.write(struct.pack("<I", tmp))
		fp.seek(tmp)
		fp.write(b"RGBs")
		while len(self.palents) < 256:
			self.palents.append([random.randint(0,255) for i in range(3)]+[0])
		assert len(self.palents) == 256
		fp.write(struct.pack("<I", len(self.palents)*4))
		paldata_ptr = fp.tell()
		for rgbs in self.palents:
			fp.write(struct.pack("<BBBB", *rgbs))

		# Patchup
		tmp = fp.tell()
		for p in palptrs:
			fp.seek(p)
			fp.write(struct.pack("<I", paldata_ptr))
		fp.seek(tmp)

		# Physdata
		fp.write(struct.pack("<I", 10))
		phys_len_ptr = fp.tell()
		fp.write(struct.pack("<I", 0))
		phys_beg = fp.tell()

		GDIVX = 20
		GDIVZ = 20
		#print(repr(self.objs))
		#print(repr(self.mdls))
		g_xmin = min(map(lambda o,m: o.px + (m.xmin<<12), self.objs, self.mdls))-0x20000
		g_zmin = min(map(lambda o,m: o.pz + (m.zmin<<12), self.objs, self.mdls))-0x20000
		g_xmax = max(map(lambda o,m: o.px + (m.xmax<<12), self.objs, self.mdls))+0x20000
		g_zmax = max(map(lambda o,m: o.pz + (m.zmax<<12), self.objs, self.mdls))+0x20000
		g_xlen = (g_xmax-g_xmin+GDIVX-1)//GDIVX
		g_zlen = (g_zmax-g_zmin+GDIVZ-1)//GDIVZ
		g_xlen = g_zlen = max(g_xlen, g_zlen) # grid must be regular!
		g_xmax = g_xmin + g_xlen*GDIVX
		g_zmax = g_zmin + g_zlen*GDIVZ
		fp.write(struct.pack("<i", g_xmin))
		fp.write(struct.pack("<i", g_zmin))
		fp.write(struct.pack("<i", g_xmax))
		fp.write(struct.pack("<i", g_zmax))
		fp.write(struct.pack("<HH", GDIVX, GDIVZ))

		for z in range(GDIVZ):
			for x in range(GDIVX):
				xmin = g_xmin + (x+0)*g_xlen
				xmax = g_xmin + (x+1)*g_xlen
				zmin = g_zmin + (z+0)*g_zlen
				zmax = g_zmin + (z+1)*g_zlen

				L = []
				for (i, (o, m,),) in enumerate(zip(self.objs, self.mdls)):
					if o.px+(m.xmax<<12) < xmin: continue
					if o.pz+(m.zmax<<12) < zmin: continue
					if o.px+(m.xmin<<12) > xmax: continue
					if o.pz+(m.zmin<<12) > zmax: continue
					L.append(i)

				fp.write(struct.pack("<II", 0, 0))
				fp.write(struct.pack("<I", len(L)))
				for n in L:
					fp.write(struct.pack("<I", n))
				fp.write(struct.pack("<I", 0))

		# Patchup for Physdata
		phys_end = fp.tell()
		fp.seek(phys_len_ptr)
		fp.write(struct.pack("<I", phys_end-phys_beg))
		fp.seek(phys_end)

		# End of chunk list
		fp.write(struct.pack("<i", -1))

		# Model names
		for (i, mdl,) in enumerate(self.mdls):
			fp.write(struct.pack("<I", 0xBEEF0000+i))

		# Texture names
		fp.write(struct.pack("<I", len(self.texs)))
		for tex in self.texs:
			fp.write(struct.pack("<I", tex.name))

		# 4bpp palettes
		p4list = list(filter(lambda x: x.bpp == 4, self.texs))
		fp.write(struct.pack("<I", len(p4list)))
		for tex in p4list:
			tex.write_palette_4bpp(fp=fp)

		# 8bpp palettes
		p8list = list(filter(lambda x: x.bpp == 8, self.texs))
		fp.write(struct.pack("<I", len(p8list)))
		for tex in p8list:
			tex.write_palette_8bpp(fp=fp)

		# Actual texture data
		fp.write(struct.pack("<I", len(self.texs)))
		texlist_ptrs = []
		texlist_ptrs_ptr = fp.tell()
		for tex in self.texs:
			fp.write(struct.pack("<I", 0))

		for tex in self.texs:
			texlist_ptrs.append(fp.tell())
			tex.write_data(fp=fp)

		tmp_texlist_ptrs = fp.tell()
		fp.seek(texlist_ptrs_ptr)
		for p in texlist_ptrs:
			fp.write(struct.pack("<I", p))
		fp.seek(tmp_texlist_ptrs)

		# Done
		fp.close()

#
# Blender specifics
#

BLEND_PER_THPS = 16

def fix24(v):
	return int(round(v*4096.0*4096.0))

def fix12(v):
	return int(round(v*4096.0))

def export_trg(trg_fname):
	fname_base = ".".join(trg_fname.split(".")[:-1])
	refname_base = fname_base.split("/")[-1].split("\\")[-1]
	trg_refname = fname_base.split("/")[-1].split("\\")[-1]
	if fname_base.lower().endswith("_t"):
		fname_base = fname_base[:-2]
	if refname_base.lower().endswith("_t"):
		refname_base = refname_base[:-2]
	psx_main_fname = fname_base + ".psx"
	psx_lib_fname = fname_base + "_l.psx"
	psx_obj_fname = fname_base + "_o.psx"
	psx_main_refname = refname_base + ""
	psx_lib_refname = refname_base + "_l"
	psx_obj_refname = refname_base + "_o"
	print("filename base:     %s" % (repr(fname_base),))
	print("filename TRG:      %s" % (repr(trg_fname),))
	print("filename PSX main: %s" % (repr(psx_main_fname),))
	print("filename PSX lib:  %s" % (repr(psx_lib_fname),))
	print("filename PSX obj:  %s" % (repr(psx_obj_fname),))
	print("ref-name base:     %s" % (repr(refname_base),))
	print("ref-name TRG:      %s" % (repr(trg_refname),))
	print("ref-name PSX main: %s" % (repr(psx_main_refname),))
	print("ref-name PSX lib:  %s" % (repr(psx_lib_refname),))
	print("ref-name PSX obj:  %s" % (repr(psx_obj_refname),))

	# Create files
	psx = PSX()
	trg = TRG()

	# Create a dummy texture
	dummytex_idx, dummyname_idx, = psx.texture(
		unk1=0,
		iw=8, ih=8,
		bpp=4,
		pal=[rgb15(128,128,128)]*16,
		data=[0x00]*(8*8//2))

	# Light all the things
	# TODO: handle non-greyscale lighting
	# TODO: autocalculate this
	palette = [[i,i,i,0] for i in range(256)]
	psx.palents = palette

	# Go through all of the lamps
	lamps = []
	for obj in bpy.data.objects:
		# Ensure that this is a lamp
		if not isinstance(obj.data, bpy.types.Lamp):
			continue

		# Get location
		locationx = obj.location.x
		locationy = obj.location.y
		locationz = obj.location.z

		# Get lamp
		lamp = obj.data

		lamps.append({
			"pos": (locationx, locationy, locationz,),
			"type": lamp.type,
		})

	# Go through the meshes and form objects
	for obj in bpy.data.objects:
		# Ensure that this is a mesh
		if not isinstance(obj.data, bpy.types.Mesh):
			continue

		# Get object + suitable transformation
		scalex = obj.scale.x
		scaley = obj.scale.y
		scalez = obj.scale.z
		locationx = obj.location.x
		locationy = obj.location.y
		locationz = obj.location.z

		# Get mesh
		mesh = obj.data

		# Get vertices
		vertices = list(map(
			lambda v:
			(
				fix12(( v.co.x*scalex+locationx)/BLEND_PER_THPS),
				fix12((-v.co.z*scalez-locationz)/BLEND_PER_THPS),
				fix12(( v.co.y*scaley+locationy)/BLEND_PER_THPS),
			),
			mesh.vertices))

		# Get centre
		xmin = min(map(lambda v: v[0], vertices))
		ymin = min(map(lambda v: v[1], vertices))
		zmin = min(map(lambda v: v[2], vertices))
		xmax = max(map(lambda v: v[0], vertices))
		ymax = max(map(lambda v: v[1], vertices))
		zmax = max(map(lambda v: v[2], vertices))
		lx = xmax-xmin
		ly = ymax-ymin
		lz = zmax-zmin
		cx = (xmin+xmax+1)>>1
		cy = (ymin+ymax+1)>>1
		cz = (zmin+zmax+1)>>1

		# Ensure it's not too big
		# TODO: autosplit models
		print(lx, ly, lz)
		assert lx <= 0xFFFE
		assert ly <= 0xFFFE
		assert lz <= 0xFFFE

		# Re-centre it
		vertices = list(map(
			lambda v:
			(v[0]-cx, v[1]-cy, v[2]-cz,),
			vertices))

		# Create model object
		mdl = psx.thing(
			px=cx<<12,
			py=cy<<12,
			pz=cz<<12)

		# Add vertices to model
		vidxs = list(map(
			lambda v:
			mdl.vertex(*v),
			vertices))
		cidxs = []
		for v in vertices:
			# Get vertex normal
			# TODO!
			#v[0]
			cidxs.append(random.randint(64,192))

		for poly in mesh.polygons:
			# Triangulate and/or Quadrilaterate
			fvlist = list(poly.vertices)

			# Perform norm correction
			v0 = vertices[fvlist[0]]
			v1 = vertices[fvlist[1]]
			v2 = vertices[fvlist[2]]
			dva = tuple(map(lambda b,a: b-a, v1, v0))
			dvb = tuple(map(lambda b,a: b-a, v2, v0))
			fnx = (dva[1]*dvb[2] - dva[2]*dvb[1])
			fny = (dva[2]*dvb[0] - dva[0]*dvb[2])
			fnz = (dva[0]*dvb[1] - dva[1]*dvb[0])
			pnx =  poly.normal.x
			pny = -poly.normal.z
			pnz =  poly.normal.y

			normdot = (0.0
				+ fnx*pnx 
				+ fny*pny 
				+ fnz*pnz)

			if normdot > 0.0:
				fvlist = fvlist[::-1]

			for i in range(0,len(fvlist)-2,2):
				i0 = fvlist[0]
				i1 = fvlist[i+1]
				i2 = fvlist[i+2]
				i3 = fvlist[i+3] if i+3 < len(fvlist) else None

				if i3 != None:
					i1, i2, i3 = i1, i3, i2

				rflags = 0x1803
				sflags = 0x0000

				if i3 == None:
					rflags |= 0x0010 # Triangle

				mdl.face(
					rflags = rflags,
					sflags = sflags,
					vidxs = [
						vidxs[i0],
						vidxs[i1],
						vidxs[i2],
						vidxs[i3] if i3 != None else 0,
					],
					#cmd = [random.randint(80,160) for i in range(3) ]+[0x24],
					#cmd = [random.randint(0,255) for i in range(4)],
					cmd = [
						cidxs[i0],
						cidxs[i1],
						cidxs[i2],
						cidxs[i3] if i3 != None else 0,
					],
					tidx = dummytex_idx,
					tpoints = [
						(0,0),
						(0,0),
						(0,0),
						(0,0),
					])

	# Add an autoexec node
	res_autoexec = trg.new_autoexec(
		ops=[
			SetFadeColor(0x8000, 0x0000),
			SetRestart("Start"),
			SetRestart2("Start"),
			SetGameLevel(0),
			#SpoolIn(psx_lib_refname),
			#SpoolIn(psx_obj_refname),
			#SetObjFile(psx_obj_refname),
			EndCommandList(), 
		])

	# Add a restart
	spawn_x = 0
	spawn_y = 0
	spawn_z = 0
	res_start = trg.new_restart(
		px=fix12(spawn_x), py=fix12(spawn_y), pz=fix12(spawn_z),
		#sx=0, sy=0xFFF&int(round((270-wad.player1.angle)*0x1000/360.0)), sz=0,
		sx=0, sy=0, sz=0,
		name="Start",
		ops=[
			SetReverbType(1),
			SetCheatRestarts("Start"),
			SetFoggingParams(10, 5500, 1024),
			SpoolEnv(psx_main_refname),
			SetOTPushback(0x400),
			SetOTPushback2(0x80),
			SetInitialPulses(1),
			SendPulse(),
			#SendSuspend(),
			#SetSkyColor(0x0004, 0x080A),
			SetSkyColor(0x0020, 0x0040),
			EndCommandList(),
		])

	# Write files
	psx.write(fname=psx_main_fname)
	trg.write(fname=trg_fname)

class THPSMapExporter(bpy.types.Operator):
	bl_idname = "export.thps_map"
	bl_label = "Export THPS TRG+PSX map"

	filepath = bpy.props.StringProperty(subtype="FILE_PATH")

	#@classmethod
	#def poll(cls, context):
	#	return context.object is not None

	def execute(self, context):
		export_trg(self.filepath)
		return {"FINISHED"}

	def invoke(self, context, event):
		context.window_manager.fileselect_add(self)
		return {"RUNNING_MODAL"}

def map_export_menu(self, context):
	self.layout.operator_context = "INVOKE_DEFAULT"
	self.layout.operator(THPSMapExporter.bl_idname, text="THPS map (*.trg)")

def register():
	bpy.utils.register_class(THPSMapExporter)
	bpy.types.INFO_MT_file_export.append(map_export_menu)

def unregister():
	bpy.types.INFO_MT_file_export.remove(map_export_menu)
	bpy.utils.unregister_class(THPSMapExporter)

