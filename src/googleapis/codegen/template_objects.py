#!/usr/bin/python2.6
# Copyright 2010 Google Inc. All Rights Reserved.
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.

"""Base classes for objects which are usable in templates.

This module contains the base classes for objects which can be used directly
in template expansion.
"""

__author__ = 'aiuto@google.com (Tony Aiuto)'

import copy

from googleapis.codegen import html_stripper
from googleapis.codegen import name_validator
from googleapis.codegen import utilities
from googleapis.codegen.django_helpers import MarkSafe


class UseableInTemplates(object):
  """Base class for any object usable in templates.

  The important feature is that they function as dicts, so that their properties
  can be referenced from django templates.
  """

  def __init__(self, def_dict):
    """Construct a UseableInTemplates object.

    Args:
      def_dict: The discovery dictionary for this element. All the values in it
          are exposed to the template expander.
    """
    self._def_dict = dict(def_dict)
    self._raw_def_dict = dict(copy.deepcopy(def_dict))

  def __getitem__(self, key):
    """Overrides default __getitem__ to return values from the original dict."""
    return self._def_dict[key]

  def GetTemplateValue(self, name):
    """Get the value for a name which might appear in a template.

    Args:
      name: (str) name of the value.
    Returns:
      object or None if not found.
    """
    return self._def_dict.get(name, None)

  def SetTemplateValue(self, name, value):
    """Adds a name/value pair to the template."""
    self._def_dict[name] = value

  def DeleteTemplateValue(self, name):
    """Delete a value from the object."""
    if name in self._def_dict:
      del self._def_dict[name]

  @property
  def values(self):
    """Return the underlying name/value pair dictionary."""
    return self._def_dict

  @property
  def raw(self):
    return self._raw_def_dict


class CodeObject(UseableInTemplates):
  """Template objects which represents an element that might be in code.

  This is the base class for things which might be code elements, such as
  classes, variables and methods.
  """

  _validator = name_validator

  def __init__(self, def_dict, api, parent=None, language_model=None):
    """Construct a CodeObject.

    Args:
      def_dict: (dict) The discovery dictionary for this element.
      api: (Api) The Api instance which owns this element.
      parent: (CodeObject) The parent of this element.
      language_model: (LanguageModel) The language we are targetting.
        Dynamically defaults to the parent's language model.
    """
    super(CodeObject, self).__init__(def_dict)
    self._api = api
    self._children = []
    self._parent = None
    self._language_model = language_model
    self._module = None
    self.SetParent(parent)
    # Sanitize the 'description'. It is a block of user written text we want to
    # emit whenever possible.
    d = def_dict.get('description')
    if d:
      self.SetTemplateValue('description',
                            self.ValidateAndSanitizeComment(self.StripHTML(d)))

  @classmethod
  def ValidateName(cls, name):
    """Validate that the name is safe to use in generated code."""
    cls._validator.Validate(name)

  @classmethod
  def ValidateAndSanitizeComment(cls, comment):
    """Remove unsafe constructions from a string and make it safe in templates.

    Make sure a string intended as a comment has only safe constructs in it and
    then make it as safe to expand directly in a template. If it fails the test,
    return an empty string.

    Args:
      comment: (str) A string which is expected to be a documentation comment.

    Returns:
      (str) The comment with HTML-unsafe constructions removed.
    """
    comment = comment.encode('ASCII', 'ignore')
    return MarkSafe(cls._validator.ValidateAndSanitizeComment(comment))

  @staticmethod
  def StripHTML(input_string):
    """Strip HTML from a string."""
    stripper = html_stripper.HTMLStripper()
    stripper.feed(input_string)
    return stripper.GetFedData()

  @property
  def api(self):
    return self._api

  @property
  def children(self):
    return self._children

  @property
  def parent(self):
    return self._parent

  @property
  def module(self):
    """Returns the module this object would belong in.

    Walks up the ancesters _module is undefined for self. If a module can not
    be found, raises an error, since this indicates either a problem building
    the API model or in writing a template. Failing silently does not help
    debug that.

    Returns:
      Module

    Raises:
      ValueError: If the module can not be determined.
    """
    if self._module:
      return self._module
    if self.parent:
      return self.parent.module
    raise ValueError('Asked for module of CodeObject without any: %s, %s' %
                     (self.values.get('wireName', '<unnamed>'), self))

  @property
  def codeName(self):  # pylint: disable-msg=C6409
    """Returns a language appropriate name for this object.

    This property should only be used during template expansion. It is computed
    once, using the LanguageModel in play, and then that value is cached.

    Returns:
      (str) a name for an instance of this object.
    """
    code_name = self.GetTemplateValue('codeName')
    if not code_name:
      code_name = self.values['wireName']
      if self.language_model:
        code_name = self.language_model.ToMemberName(code_name, self._api)
      self.SetTemplateValue('codeName', code_name)
    return MarkSafe(code_name)

  @property
  def fullClassName(self):  # pylint: disable-msg=C6409
    """Returns the fully qualified class name for this object.

    This property can only be used during template expansion.  Walks up the
    parent chain building a fully qualified class name. If the object is in a
    module, include the module name.

    Returns:
      (str) The class name of this object.
    """
    module = self.module
    if module:
      class_name_delimiter = self.language_model.class_name_delimiter
      return module.name + class_name_delimiter + self.RelativeClassName(None)
    return MarkSafe(self.RelativeClassName(None))

  @property
  def packageRelativeClassName(self):  # pylint: disable-msg=C6409
    """Returns the class name for this object relative to its package.

    Walks up the parent chain building a fully qualified class name.

    Returns:
      (str) The class name of this object.
    """
    return MarkSafe(self.RelativeClassName(None))

  def RelativeClassName(self, other):
    """Returns the class name for this object relative to another.

    This property can only be used during template expansion.

    Args:
      other: (CodeObject) Another code object which might be a parent.
    Returns:
      (str) The class name of this object relative to another.
    """
    if self == other:
      return ''
    full_name = ''
    if self.parent:
      full_name = self.parent.RelativeClassName(other)
    if full_name:
      language_model = self.language_model
      if language_model:
        class_name_delimiter = language_model.class_name_delimiter
      full_name += class_name_delimiter
    full_name += (self.values.get('className')
                  or self.values.get('codeName')
                  or self.values.get('name', ''))
    return full_name

  @property
  def parentPath(self):  # pylint: disable-msg=C6409
    """Returns the classNames from my ultimate parent to my immediate parent.

    Walks up the parent chain building a list of ancestors.

    TODO(user): Eliminate this routine by adding template tags which
    let me process the ancestor list directly.

    Returns:
      (list) The class name of this object.
    """
    parent_list = self.ancestors
    return [p.values.get('className') for p in parent_list]

  @property
  def ancestors(self):
    """Return the objects from my ultimate parent down to my immediate parent.

    Returns:
      (list) list of CodeObjects.
    """
    if self.parent:
      return self.parent.ancestors + [self.parent]
    return []

  @property
  def full_path(self):
    """Return the objects from my ultimate parent down to me.

    Returns:
      (list) list of CodeObjects.
    """
    return (self.ancestors or []) + [self]

  def FindTopParent(self):
    if self.parent:
      return self.parent.FindTopParent()
    return self

  def SetLanguageModel(self, language_model):
    """Changes the language model of this code object."""
    self._language_model = language_model

  def SetParent(self, parent):
    """Changes the parent of this code object.

    Args:
      parent: (CodeObject) the new parent.
    """
    if self._parent:
      self._parent.children.remove(self)
    self._parent = parent
    if self._parent:
      self._parent.children.append(self)

  @property
  def language_model(self):
    """Returns the nearest LanguageModel by walking my parents.

    Memoizes the computation, by setting self._language_model after the first
    parent lookup.

    Returns:
      (LanguageModel) A LanguageModel
    """
    if self._language_model:
      return self._language_model
    if self._parent:
      self._language_model = self._parent.language_model
    return self._language_model

  @property
  def codeType(self):  # pylint: disable-msg=C6409
    """Accessor for codeType for use in templates.

    If the template value for codeType was explicitly set, return that,
    otherwise use the code_type member. This is only safe to call for code
    objects which implement code_type.

    Returns:
      (str) the value for codeType
    """
    return MarkSafe(self.GetTemplateValue('codeType') or self.code_type)

  @property
  def safeCodeType(self):  # pylint: disable-msg=C6409
    """Expose this in template using the template naming convention.

    Just redirect to safe_code_type.

    Returns:
      (str) The evaluated code type.
    """
    return MarkSafe(self.safe_code_type)


class Module(CodeObject):
  """A code object which represents the concept of a module.

  A Module has two properties available for use in templates:
    name: The full name of this module, including the parent of this Module.
    path: The file path where this module would be stored in a full generated
          code layout. Since the templates can not open files for writing, this
          is intended for use inside documentation.

  These values are derived from elements defining the owner of the API or
  shared data type as described in http://goto/apiarylibrarynamespacing

  Typically, a code generator will create a model (e.g. an Api) and assign a
  a Module to the top node. Other nodes in the model might be in different
  modules, which can be created as children of the top Module. E.g.
    api = LoadApi(....)
    top_module = Module(... api owner information ...)
    api_module = Module(api.name, parent=top_module)
    api._module = api_module
    model_module = Module('model', parent=api_module)
    for s in api.schemas:
      s._module = model_module

  Shared data types contain information that specify the module they belong to,
  which may be different from the module for the API itself.

  Modules are mutable up until the first time the name or path properties
  are evaluated.
  """

  def __init__(self, path=None, owner_name=None, owner_domain=None, parent=None,
               language_model=None):
    """Construct a Module.

    Args:
      path: (str) A '/' delimited path to this module.
      owner_name: (str) The name of the owner of the API, as they would like it
        to appear in library code. E.g "Best Buy"
      owner_domain: (str) The domain of the owner of the API, as they would like
        it to appear in library code.
      parent: (CodeObject) The parent of this element.
      language_model: (LanguageModel) The language we are targetting.
        Dynamically defaults to the parent's language model.
    """
    super(Module, self).__init__({}, None,
                                 parent=parent,
                                 language_model=language_model)
    self._path = path
    self._owner_name = owner_name
    self._owner_domain = utilities.SanitizeDomain(owner_domain)
    self._name = None  # will be memoized on first call to name property

  @classmethod
  def ModuleFromDictionary(cls, def_dict):
    """Returns a Module corresponding the library_definition of an object.

    If there is a 'library_definition' section in the given dictionary, use it
    to construct a Module from that information. Return None if there is no
    definition.

    Args:
      def_dict: (dict) Discovery style object definition.
    Returns:
      Module or None.
    """
    lib_def = def_dict.get('library_definition')
    if not lib_def:
      return None
    return Module(path=lib_def.get('modulePath') or '',
                  owner_name=lib_def.get('owner'),
                  owner_domain=lib_def.get('domain'))

  def SetPath(self, path):
    """Changes the path for this module.

    May be called up until the first time we ask for the module name. This
    restriction is to detect a class of coding errors which could occur if we
    incorrectly share the Module across types of different parentage.

    Args:
      path: (str) Path for this module ('/' delimited).

    Raises:
      ValueError: if called after the name or path properties have been evaled.
    """
    if self._name:
      raise ValueError('SetPath called after first use of name property')
    self._path = path

  @property
  def name(self):
    """Returns the language appropriate name for a module."""
    if not self._name:
      self._name = self.path.replace(
          '/', self.language_model.module_name_delimiter)
    return self._name

  @property
  def path(self):
    """Returns the / delimited file path for this package."""
    if self.parent:
      base_path = self.parent.path
    else:
      base_path = self.language_model.DefaultContainerPathForOwner(
          self._owner_name, self._owner_domain)
    return '/'.join(x for x in (base_path, self._path) if x)


class DataValue(CodeObject):
  """Provide a reasonable value wrapper for converting types to strings."""

  def __init__(self, value, val_type):
    # Because val_type could be a schema and DataObject tries to deepcopy
    # the definition dictionary when schemas store CodeObjects in their
    # _def_dicts. Sidestep this part.
    super(DataValue, self).__init__(
        {}, api=val_type.api, parent=val_type.parent)
    self._def_dict = val_type.values

    # Type may be passed in wrapped in a Property/Parameter object...
    if hasattr(val_type, 'data_type'):
      data_type = val_type.data_type
    else:
      data_type = val_type

    # Type may be a reference, we want the real thing...
    # TODO(user): 20130227
    # If you need this trickery here, we are doing something wrong in the
    # overall structure.
    data_type = getattr(data_type, 'referenced_schema', data_type)

    self._value = value
    self._data_type = data_type
    self._metadata = {}

  def SetValue(self, value):
    self._value = value

  def SetLanguageModel(self, language_model):
    super(DataValue, self).SetLanguageModel(language_model)
    self.data_type.SetLanguageModel(language_model)

  def GetLanguageModel(self):
    # pylint: disable-msg=W0212
    return self.data_type.language_model

  @property
  def value(self):
    return self._value

  @property
  def data_type(self):
    return self._data_type

  @property
  def code_type(self):
    # Certain data types return a code_type dependent on language model...
    # so we assure that our data_type uses the correct one for safety.
    if self._language_model:
      self._data_type.SetLanguageModel(self._language_model)
    return self._data_type.code_type

  @property
  def metadata(self):
    return self._metadata