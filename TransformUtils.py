#!/usr/bin/env python

# Author: Nick R. Rypkema (rypkema@mit.edu)
# License: MIT

'''
The LightField Visualizer - a VTK/PyQt4-based lightweight field robotics viewer
-------------------------------------------------------------------------------
transformation utilities
'''

''' standard libs '''
import math
import warnings
import numpy as np

''' VTK '''
import vtk
from vtk.util import numpy_support as nps

''' custom libs '''
import Billboards

''' thirdparty libs '''
from thirdparty import transformations

def ApplyTransformation(actor_transform, numpy_translation, numpy_rotation, order=1, post=False):
    # order: 0 -> rotation then translation | 1 -> translation then rotation
    if post:
        actor_transform.PostMultiply()
    else:
        actor_transform.PreMultiply()
    if order == 0:
        if numpy_rotation is not None:
            actor_transform.Concatenate(numpy_rotation.flatten().tolist())
        if numpy_translation is not None:
            actor_transform.Concatenate(numpy_translation.flatten().tolist())
    else:
        if numpy_translation is not None:
            actor_transform.Concatenate(numpy_translation.flatten().tolist())
        if numpy_rotation is not None:
            actor_transform.Concatenate(numpy_rotation.flatten().tolist())
    return actor_transform

def ApplyTransformationEuler(actor_transform, x_translate, y_translate, z_translate, roll, pitch, yaw, order=1, post=False):
    numpy_translation = transformations.translation_matrix([x_translate, y_translate, z_translate])
    numpy_rotation = transformations.euler_matrix(math.radians(roll), math.radians(pitch), math.radians(yaw))
    actor_transform = ApplyTransformation(actor_transform, numpy_translation, numpy_rotation, order, post)
    return actor_transform


''' from RobotLocomotion/director - transformUtils.py (Pat Marion) '''

def getTransformFromNumpy(mat):
    '''
    Given a numpy 4x4 array, return a vtkTransform.
    '''
    assert mat.shape == (4,4)
    t = vtk.vtkTransform()
    t.SetMatrix(mat.flatten())
    return t

def getNumpyFromTransform(transform):
    '''
    Given a vtkTransform, return a numpy 4x4 array
    '''
    mat = transform.GetMatrix()
    a = np.zeros((4,4))

    for r in xrange(4):
        for c in xrange(4):
            a[r][c] = mat.GetElement(r, c)

    return a

def getTransformFromAxes(xaxis, yaxis, zaxis):
    t = vtk.vtkTransform()
    m = vtk.vtkMatrix4x4()

    axes = np.array([xaxis, yaxis, zaxis]).transpose().copy()
    vtk.vtkMath.Orthogonalize3x3(axes, axes)

    for r in xrange(3):
        for c in xrange(3):
            m.SetElement(r, c, axes[r][c])

    t.SetMatrix(m)
    return t

def getTransformFromAxesAndOrigin(xaxis, yaxis, zaxis, origin):
    t = getTransformFromAxes(xaxis, yaxis, zaxis)
    t.PostMultiply()
    t.Translate(origin)
    return t

def getAxesFromTransform(t):
    xaxis = np.array(t.TransformNormal(1,0,0))
    yaxis = np.array(t.TransformNormal(0,1,0))
    zaxis = np.array(t.TransformNormal(0,0,1))
    return xaxis, yaxis, zaxis

def getLookAtTransform(lookAtPosition, lookFromPosition, viewUp=[0.0, 0.0, 1.0]):
    xaxis = np.array(lookAtPosition) - np.array(lookFromPosition)
    if np.linalg.norm(xaxis) < 1e-8:
        xaxis = [1.0, 0.0, 0.0]
    zaxis = np.array(viewUp)
    xaxis /= np.linalg.norm(xaxis)
    zaxis /= np.linalg.norm(zaxis)
    yaxis = np.cross(zaxis, xaxis)
    yaxis /= np.linalg.norm(yaxis)
    zaxis = np.cross(xaxis, yaxis)
    return getTransformFromAxesAndOrigin(xaxis, yaxis, zaxis, lookFromPosition)

def concatenateTransforms(transformList):
    '''
    Given a list of vtkTransform objects, returns a new vtkTransform
    which is a concatenation of the whole list using vtk post multiply.
    See documentation for vtkTransform::PostMultiply.
    '''
    result = vtk.vtkTransform()
    result.PostMultiply()
    for t in transformList:
        result.Concatenate(t)
    return result

def findTransformAxis(transform, referenceVector):
    '''
    Given a vtkTransform and a reference vector, find a +/- axis of the transform
    that most closely matches the reference vector.  Returns the matching axis
    index, axis, and sign.
    '''
    refAxis = referenceVector / np.linalg.norm(referenceVector)
    axes = getAxesFromTransform(transform)

    axisProjections = np.array([np.abs(np.dot(axis, refAxis)) for axis in axes])
    matchIndex = axisProjections.argmax()
    matchAxis = axes[matchIndex]
    matchSign = np.sign(np.dot(matchAxis, refAxis))
    return matchIndex, matchAxis, matchSign

def getTransformFromOriginAndNormal(origin, normal, normalAxis=2):
    normal = np.array(normal)
    normal /= np.linalg.norm(normal)

    axes = [[0,0,0],
            [0,0,0],
            [0,0,0]]

    axes[normalAxis] = normal

    vtk.vtkMath.Perpendiculars(axes[normalAxis], axes[(normalAxis+1) % 3], axes[(normalAxis+2) % 3], 0)
    t = getTransformFromAxes(*axes)
    t.PostMultiply()
    t.Translate(origin)
    return t

def orientationFromNormal(normal):
    '''
    Creates a frame where the Z axis points in the direction of the given normal.
    '''
    zaxis = normal
    xaxis = [0,0,0]
    yaxis = [0,0,0]

    vtk.vtkMath.Perpendiculars(zaxis, xaxis, yaxis, 0)

    return orientationFromAxes(xaxis, yaxis, zaxis)

def orientationFromAxes(xaxis, yaxis, zaxis):
    t = getTransformFromAxes(xaxis, yaxis, zaxis)
    return rollPitchYawFromTransform(t)

def rollPitchYawFromTransform(t):
    pos, quat = poseFromTransform(t)
    return quaternionToRollPitchYaw(quat)

def frameInterpolate(trans_a, trans_b, weight_b):
    '''
    Interpolate two frames where weight_b=[0,1]
    '''
    [pos_a, quat_a] = poseFromTransform(trans_a)
    [pos_b, quat_b] = poseFromTransform(trans_b)
    pos_c = pos_a *(1-weight_b) + pos_b * weight_b;
    quat_c = transformations.quaternion_slerp(quat_a, quat_b, weight_b)
    return transformFromPose(pos_c, quat_c)

def transformFromPose(position, quaternion):
    '''
    Returns a vtkTransform
    '''
    mat = transformations.quaternion_matrix(quaternion)
    mat[:3,3] = position
    return getTransformFromNumpy(mat)

def poseFromTransform(transform):
    '''
    Returns position, quaternion
    '''
    mat = getNumpyFromTransform(transform)
    return np.array(mat[:3,3]), transformations.quaternion_from_matrix(mat, isprecise=True)

def frameFromPositionAndRPY(position, rpy):
    '''
    rpy specified in degrees
    '''
    rpy = np.radians(rpy)
    mat = transformations.euler_matrix(rpy[0], rpy[1], rpy[2])
    mat[:3,3] = position
    return getTransformFromNumpy(mat)

def rollPitchYawToQuaternion(rpy):
    return transformations.quaternion_from_euler(rpy[0], rpy[1], rpy[2])

def quaternionToRollPitchYaw(quat):
    return transformations.euler_from_quaternion(quat)

def copyFrame(transform):
    t = vtk.vtkTransform()
    t.PostMultiply()
    t.SetMatrix(transform.GetMatrix())
    return t