#!/usr/bin/env python
# -*- coding: UTF-8 -*-
# File: conv2d.py
# Author: Yuxin Wu <ppwwyyxx@gmail.com>

import tensorflow as tf
from ._common import layer_register, shape2d, shape4d
from ..utils import logger

__all__ = ['Conv2D', 'Deconv2D']


@layer_register()
def Conv2D(x, out_channel, kernel_shape,
           padding='SAME', stride=1,
           W_init=None, b_init=None,
           nl=None, split=1, use_bias=True):
    """
    2D convolution on 4D inputs.

    :param input: a tensor of shape NHWC
    :param out_channel: number of output channel
    :param kernel_shape: (h, w) or a int
    :param stride: (h, w) or a int. default to 1
    :param padding: 'valid' or 'same'. default to 'same'
    :param split: split channels as used in Alexnet. Default to 1 (no split)
    :param W_init: initializer for W. default to `xavier_initializer_conv2d`.
    :param b_init: initializer for b. default to zero initializer.
    :param nl: nonlinearity
    :param use_bias: whether to use bias. a boolean default to True
    :returns: a NHWC tensor
    """
    in_shape = x.get_shape().as_list()
    in_channel = in_shape[-1]
    assert in_channel is not None, "[Conv2D] Input cannot have unknown channel!"
    assert in_channel % split == 0
    assert out_channel % split == 0

    kernel_shape = shape2d(kernel_shape)
    padding = padding.upper()
    filter_shape = kernel_shape + [in_channel / split, out_channel]
    stride = shape4d(stride)

    if W_init is None:
        W_init = tf.contrib.layers.variance_scaling_initializer()
    if b_init is None:
        b_init = tf.constant_initializer()

    W = tf.get_variable('W', filter_shape, initializer=W_init)
    if use_bias:
        b = tf.get_variable('b', [out_channel], initializer=b_init)

    if split == 1:
        conv = tf.nn.conv2d(x, W, stride, padding)
    else:
        # TODO rename to split later
        inputs = tf.split_v(x, split, 3)
        kernels = tf.split_v(W, split, 3)
        outputs = [tf.nn.conv2d(i, k, stride, padding)
                   for i, k in zip(inputs, kernels)]
        conv = tf.concat_v2(outputs, 3)
    if nl is None:
        logger.warn(
            "[DEPRECATED] Default ReLU nonlinearity for Conv2D and FullyConnected will be deprecated. "
            "Please use argscope instead.")
        nl = tf.nn.relu
    return nl(tf.nn.bias_add(conv, b) if use_bias else conv, name='output')


class StaticDynamicShape(object):

    def __init__(self, static, dynamic):
        self.static = static
        self.dynamic = dynamic

    def apply(self, f):
        try:
            st = f(self.static)
            return StaticDynamicShape(st, st)
        except:
            return StaticDynamicShape(None, f(self.dynamic))


@layer_register()
def Deconv2D(x, out_shape, kernel_shape,
             stride, padding='SAME',
             W_init=None, b_init=None,
             nl=tf.identity, use_bias=True):
    """
    2D deconvolution on 4D inputs.

    :param input: a tensor of shape NHWC
    :param out_shape: either (h, w, channel), or just channel,
        then h, w will calculated by input_shape * stride
    :param kernel_shape: (h, w) or a int
    :param stride: (h, w) or a int
    :param padding: 'valid' or 'same'. default to 'same'
    :param W_init: initializer for W. default to `xavier_initializer_conv2d`.
    :param b_init: initializer for b. default to zero initializer.
    :param nl: nonlinearity.
    :param use_bias: whether to use bias. a boolean default to True
    :returns: a NHWC tensor
    """
    in_shape = x.get_shape().as_list()[1:]
    in_channel = in_shape[-1]
    assert in_channel is not None, "[Deconv2D] Input cannot have unknown channel!"
    kernel_shape = shape2d(kernel_shape)
    stride2d = shape2d(stride)
    stride4d = shape4d(stride)
    padding = padding.upper()

    if isinstance(out_shape, int):
        out_channel = out_shape
        shp3_0 = StaticDynamicShape(in_shape[0], tf.shape(x)[1]).apply(lambda x: stride2d[0] * x)
        shp3_1 = StaticDynamicShape(in_shape[1], tf.shape(x)[2]).apply(lambda x: stride2d[1] * x)
        shp3_dyn = [shp3_0.dynamic, shp3_1.dynamic, out_channel]
        shp3_static = [shp3_0.static, shp3_1.static, out_channel]
    else:
        for k in out_shape:
            if not isinstance(k, int):
                raise ValueError("[Deconv2D] out_shape is invalid!")
        out_channel = out_shape[-1]
        shp3_static = shp3_dyn = out_shape
    filter_shape = kernel_shape + [out_channel, in_channel]

    if W_init is None:
        W_init = tf.contrib.layers.xavier_initializer_conv2d()
    if b_init is None:
        b_init = tf.constant_initializer()
    W = tf.get_variable('W', filter_shape, initializer=W_init)
    if use_bias:
        b = tf.get_variable('b', [out_channel], initializer=b_init)

    out_shape_dyn = tf.stack([tf.shape(x)[0]] + shp3_dyn)
    conv = tf.nn.conv2d_transpose(x, W, out_shape_dyn, stride4d, padding=padding)
    conv.set_shape(tf.TensorShape([None] + shp3_static))
    return nl(tf.nn.bias_add(conv, b) if use_bias else conv, name='output')
