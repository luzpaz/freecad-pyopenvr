import time
import sdl2
import openvr
import numpy
from threading import Thread

from OpenGL.GL import *
from sdl2 import *

from pivy.coin import SoSeparator
from pivy.coin import SoGroup
from pivy.coin import SoBaseColor
from pivy.coin import SbColor
from pivy.coin import SoSceneManager
from pivy.coin import SbViewportRegion
from pivy.coin import SoFrustumCamera
from pivy.coin import SbVec3f
from pivy.coin import SoCamera
from pivy.coin import SoDirectionalLight
from pivy.coin import SoCone
from pivy.coin import SoTranslation
from pivy.coin import SbRotation
from pivy.coin import SoScale

from math import sqrt, copysign

# see https://github.com/cmbruns/pyopenvr

class OpenVRTest(object):
  "FreeCAD OpenVR testing script"

  def __init__(self):
    self._running = True

  def setupscene(self):
    #coin3d setup
    vpRegion = SbViewportRegion(self.w, self.h)
    self.m_sceneManager = SoSceneManager()
    self.m_sceneManager.setViewportRegion(vpRegion)
    self.m_sceneManager.setBackgroundColor(SbColor(0.0, 0.0, 0.8));
    light = SoDirectionalLight()
    light2 = SoDirectionalLight()
    light2.direction.setValue(-1,-1,-1)
    light2.intensity.setValue(0.6)
    light2.color.setValue(0.8,0.8,1)
    self.scale = SoScale()
    self.scale.scaleFactor.setValue(0.001, 0.001, 0.001) #OpenVR uses meters not milimeters
    self.camtrans0 = SoTranslation()
    self.camtrans1 = SoTranslation()
    self.cgrp0 = SoGroup()
    self.cgrp1 = SoGroup()
    self.sgrp0 = SoGroup()
    self.sgrp1 = SoGroup()
    self.camtrans0.translation.setValue([self.camToHead[0][0][3],0,0])
    self.camtrans1.translation.setValue([self.camToHead[1][0][3],0,0])
    sg = FreeCADGui.ActiveDocument.ActiveView.getSceneGraph()#get active scenegraph
    #LEFT EYE
    self.rootScene0 = SoSeparator()
    self.rootScene0.ref()
    self.rootScene0.addChild(self.cgrp0)
    self.cgrp0.addChild(self.camtrans0)
    self.cgrp0.addChild(self.camera0)
    self.rootScene0.addChild(self.sgrp0)
    self.sgrp0.addChild(light)
    self.sgrp0.addChild(light2)
    self.sgrp0.addChild(self.scale)
    self.sgrp0.addChild(sg)#add scenegraph
    #RIGHT EYE
    self.rootScene1 = SoSeparator()
    self.rootScene1.ref()
    self.rootScene1.addChild(self.cgrp1)
    self.cgrp1.addChild(self.camtrans1)
    self.cgrp1.addChild(self.camera1)
    self.rootScene1.addChild(self.sgrp1)
    self.sgrp1.addChild(light)
    self.sgrp1.addChild(light2)
    self.sgrp1.addChild(self.scale)
    self.sgrp1.addChild(sg)#add scenegraph

  def setupcameras(self):
    nearZ = self.nearZ
    farZ = self.farZ
    #LEFT EYE
    self.camera0 = SoFrustumCamera()
    self.basePosition0 = SbVec3f(0.0, 0.0, 0.0)
    self.camera0.position.setValue(self.basePosition0)
    self.camera0.viewportMapping.setValue(SoCamera.LEAVE_ALONE)
    left = nearZ * self.proj_raw[0][0]
    right = nearZ * self.proj_raw[0][1]
    top = nearZ * self.proj_raw[0][3] #top and bottom are reversed https://github.com/ValveSoftware/openvr/issues/110
    bottom = nearZ * self.proj_raw[0][2]
    aspect = (2 * nearZ / (top - bottom)) / (2 * nearZ * (right - left))
    self.camera0.nearDistance.setValue(nearZ)
    self.camera0.farDistance.setValue(farZ)
    self.camera0.left.setValue(left)
    self.camera0.right.setValue(right)
    self.camera0.top.setValue(top)
    self.camera0.bottom.setValue(bottom)
    self.camera0.aspectRatio.setValue(aspect)
    #RIGHT EYE
    self.camera1 = SoFrustumCamera()
    self.basePosition1 = SbVec3f(0.0, 0.0, 0.0)
    self.camera1.position.setValue(self.basePosition1)
    self.camera1.viewportMapping.setValue(SoCamera.LEAVE_ALONE)
    left = nearZ * self.proj_raw[1][0]
    right = nearZ * self.proj_raw[1][1]
    top = nearZ * self.proj_raw[1][3]
    bottom = nearZ * self.proj_raw[1][2]
    aspect = (2 * nearZ / (top - bottom)) / (2 * nearZ * (right - left))
    self.camera1.nearDistance.setValue(nearZ)
    self.camera1.farDistance.setValue(farZ)
    self.camera1.left.setValue(left)
    self.camera1.right.setValue(right)
    self.camera1.top.setValue(top)
    self.camera1.bottom.setValue(bottom)
    self.camera1.aspectRatio.setValue(aspect)
  
  def extractrotation(self, transfmat): #extract rotation quaternion
    qw = sqrt(numpy.fmax(0, 1 + transfmat[0][0] + transfmat[1][1] + transfmat[2][2])) / 2
    qx = sqrt(numpy.fmax(0, 1 + transfmat[0][0] - transfmat[1][1] - transfmat[2][2])) / 2
    qy = sqrt(numpy.fmax(0, 1 - transfmat[0][0] + transfmat[1][1] - transfmat[2][2])) / 2
    qz = sqrt(numpy.fmax(0, 1 - transfmat[0][0] - transfmat[1][1] + transfmat[2][2])) / 2
    qx = copysign(qx, transfmat[2][1] - transfmat[1][2]);
    qy = copysign(qy, transfmat[0][2] - transfmat[2][0])
    qz = copysign(qz, transfmat[1][0] - transfmat[0][1])
    hmdrot = SbRotation(qx, qy, qz, qw)
    return hmdrot
    
  def extracttranslation(self, transfmat):
    hmdpos = SbVec3f(transfmat[0][3], transfmat[1][3], transfmat[2][3])
    return hmdpos
      
  def draw(self):
    #self.vr_compositor.waitGetPoses(self.poses, openvr.k_unMaxTrackedDeviceCount, None, 0)
    self.vr_compositor.waitGetPoses(self.poses, None)
    headPose = self.poses[openvr.k_unTrackedDeviceIndex_Hmd]
    if not headPose.bPoseIsValid:
      return True

    headToWorld = headPose.mDeviceToAbsoluteTracking
    transfmat = numpy.array([ [headToWorld.m[j][i] for i in range(4)] for j in range(3) ])
    hmdrot = self.extractrotation(transfmat)
    hmdpos = self.extracttranslation(transfmat)
    self.camera0.orientation.setValue(hmdrot)
    self.camera0.position.setValue(self.basePosition0 + hmdpos)
    self.camera1.orientation.setValue(hmdrot)
    self.camera1.position.setValue(self.basePosition1 + hmdpos)

    for eye in range(2):
      glBindFramebuffer(GL_FRAMEBUFFER, self.frame_buffers[eye])
      #coin3d rendering
      glUseProgram(0)
      if eye == 0:
        self.m_sceneManager.setSceneGraph(self.rootScene0)
      if eye == 1:
        self.m_sceneManager.setSceneGraph(self.rootScene1)
      glEnable(GL_CULL_FACE)
      glEnable(GL_DEPTH_TEST)
      self.m_sceneManager.render()
      glDisable(GL_CULL_FACE)
      glDisable(GL_DEPTH_TEST)
      glClearDepth(1.0)
      #end coin3d rendering
      self.vr_compositor.submit(self.eyes[eye], self.textures[eye])
    return True

  def run(self):
    self.vr_system = openvr.init(openvr.VRApplication_Scene)
    self.vr_compositor = openvr.VRCompositor()
    poses_t = openvr.TrackedDevicePose_t * openvr.k_unMaxTrackedDeviceCount
    self.poses = poses_t()
    self.w, self.h = self.vr_system.getRecommendedRenderTargetSize()
    SDL_Init(SDL_INIT_VIDEO)
    self.window = SDL_CreateWindow (b"test",
      SDL_WINDOWPOS_CENTERED, SDL_WINDOWPOS_CENTERED,
      100, 100, SDL_WINDOW_SHOWN|SDL_WINDOW_OPENGL)
    self.context = SDL_GL_CreateContext(self.window)
    SDL_GL_MakeCurrent(self.window, self.context)
    self.depth_buffer = glGenRenderbuffers(1)
    self.frame_buffers = glGenFramebuffers(2)
    self.texture_ids = glGenTextures(2)
    self.textures = [None] * 2
    self.eyes = [openvr.Eye_Left, openvr.Eye_Right] 
    self.camToHead = [None] * 2
    self.proj_raw = [None] * 2
    self.nearZ = 0.01
    self.farZ = 500

    for eye in range(2):
      glBindFramebuffer(GL_FRAMEBUFFER, self.frame_buffers[eye])
      glBindRenderbuffer(GL_RENDERBUFFER, self.depth_buffer)
      glRenderbufferStorage(GL_RENDERBUFFER, GL_DEPTH24_STENCIL8, self.w, self.h)
      glFramebufferRenderbuffer(
        GL_FRAMEBUFFER, GL_DEPTH_STENCIL_ATTACHMENT, GL_RENDERBUFFER,
        self.depth_buffer)
      glBindTexture(GL_TEXTURE_2D, self.texture_ids[eye])
      glTexImage2D(
        GL_TEXTURE_2D, 0, GL_RGBA8, self.w, self.h, 0, GL_RGBA, GL_UNSIGNED_BYTE,
        None)
      glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
      glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
      glFramebufferTexture2D(
        GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0, GL_TEXTURE_2D,
        self.texture_ids[eye], 0)
      texture = openvr.Texture_t()
      texture.handle = int(self.texture_ids[eye])
      texture.eType = openvr.TextureType_OpenGL
      texture.eColorSpace = openvr.ColorSpace_Gamma
      self.textures[eye] = texture
      self.proj_raw[eye]= self.vr_system.getProjectionRaw(self.eyes[eye]) #void GetProjectionRaw( Hmd_Eye eEye, float *pfLeft, float *pfRight, float *pfTop, float *pfBottom )
      eyehead = self.vr_system.getEyeToHeadTransform(self.eyes[eye]) #[0][3] is eye-center distance
      self.camToHead[eye] = numpy.array([ [eyehead.m[j][i] for i in range(4)] for j in range(3) ]) 

    self.setupcameras()
    self.setupscene()
    while self._running:
      self.draw()

  def terminate(self):
    self._running = False
    glDeleteBuffers(1, [self.depth_buffer])
    for eye in range(2):
      glDeleteBuffers(1, [self.frame_buffers[eye]])
    openvr.shutdown()

if __name__ == "__main__":
  ovrtest = OpenVRTest()
  t = Thread(target=ovrtest.run)
  t.start() #type ovrtest.terminate() to stop
