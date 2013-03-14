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

"""Java library generator.

Specializations to the code Generator for Java bindings. This class also serves
as a superclass for GWT generation, since that shares Java's naming rules.
"""

__author__ = 'aiuto@google.com (Tony Aiuto)'

from googleapis.codegen import api
from googleapis.codegen import api_library_generator
from googleapis.codegen import data_types
from googleapis.codegen import utilities
from googleapis.codegen.import_definition import ImportDefinition
from googleapis.codegen.java_import_manager import JavaImportManager
from googleapis.codegen.language_model import LanguageModel


class BaseJavaGenerator(api_library_generator.ApiLibraryGenerator):
  """Base for Java code generators."""

  _support_prop_methods = True

  def __init__(self, discovery, language='java', language_model=None,
               options=None):
    if not language_model:
      language_model = self._GetDefaultLanguageModel()
    super(BaseJavaGenerator, self).__init__(JavaApi, discovery, language,
                                            language_model, options=options)

  @classmethod
  def _GetDefaultLanguageModel(cls):
    return JavaLanguageModel()

  def _InnerModelClassesSupported(self):
    """Gets whether or not inner model classes are supported."""
    return True

  def AnnotateApi(self, the_api):
    """Annotate the Api dictionary with Java specifics."""
    pass

  def AnnotateMethod(self, the_api, method, resource):
    """Annotate a Method with Java specific elements.

    We add a few things:
    * Annotate our parameters
    * Constructor declaration lists.  We do it here rather than in a template
      mainly because it is much easier to do the join around the ','
    * Add a 'content' member for PUT/POST methods which take an object as input.

    Args:
      the_api: (Api) The API tree which owns this method.
      method: (Method) The method to annotate.
      resource: (Resource) The resource which owns this method.
    """
    # Chain up so our parameters are annotated first.
    super(BaseJavaGenerator, self).AnnotateMethod(the_api, method, resource)
    if not self._support_prop_methods:
      # TODO(user): This is a hack until the Java client supports the
      # PROP methods
      http_method = method.values.get('httpMethod')
      if (http_method == 'PROPFIND' or http_method == 'OPTIONS'
          or http_method == 'REPORT'):
        method.SetTemplateValue('httpMethodOverride', http_method)
        method.SetTemplateValue('httpMethod', 'GET')
      if method == 'PROPPATCH':
        method.SetTemplateValue('httpMethodOverride', http_method)
        method.SetTemplateValue('httpMethod', 'PATCH')

  def AnnotateParameter(self, unused_method, parameter):
    """Annotate a Parameter with Java specific elements."""
    self._HandleImports(parameter)

  def AnnotateProperty(self, unused_api, prop, unused_schema):
    """Annotate a Property with Java specific elements."""
    self._HandleImports(prop)

  def _HandleImports(self, element):
    """Handles imports for the specified element.

    Args:
      element: (Property|Parameter) The property we want to set the import for.
    """
    # Get the parent of this Property/Parameter.
    parent = element.schema
    if self._InnerModelClassesSupported():
      # If inner classes are supported find the top level parent to set
      # imports for.
      while parent.parent:
        parent = parent.parent
    import_manager = JavaImportManager.GetCachedImportManager(parent)

    # For collections, we have to get the imports for the first non-collection
    # up the base_type chain.
    data_type = element.data_type
    json_type = data_type.json_type
    while json_type == 'array' or json_type == 'map':
      data_type = data_type._base_type  # pylint: disable-msg=protected-access
      json_type = data_type.json_type
    json_format = data_type.values.get('format')

    type_format_to_datatype_and_imports = self.language_model.type_map
    datatype_and_imports = (
        type_format_to_datatype_and_imports.get((json_type, json_format)))
    if datatype_and_imports:
      import_definition = datatype_and_imports[1]
      # Import all required imports.
      for required_import in import_definition.imports:
        import_manager.AddImport(required_import)
      # Set all template values, if specified.
      for template_value in import_definition.template_values:
        element.SetTemplateValue(template_value, True)


class Java8Generator(BaseJavaGenerator):
  """A Java generator for language version 1.8."""
  _support_prop_methods = False

  @classmethod
  def _GetDefaultLanguageModel(cls):
    return Java8LanguageModel()


class Java12Generator(BaseJavaGenerator):
  """A Java generator for language version 1.12 and 1.13."""


class Java14Generator(BaseJavaGenerator):
  """A Java generator for language version 1.14 and higher."""

  @classmethod
  def _GetDefaultLanguageModel(cls):
    return Java14LanguageModel()

  def AnnotateParameter(self, unused_method, parameter):
    """Annotate a Parameter with Java specific elements."""
    self._HandleJsonString(parameter)

  def AnnotateProperty(self, unused_api, prop, unused_schema):
    """Annotate a Property with Java specific elements."""
    self._HandleJsonString(prop)

  def _HandleJsonString(self, element):
    """Handles imports for the specified element.

    Args:
      element: (Property|Parameter) The property we want to set the import for.
    """
    # For collections, we have to get the imports for the first non-collection
    # up the base_type chain.
    data_type = element.data_type
    json_type = data_type.json_type
    while json_type == 'array' or json_type == 'map':
      data_type = data_type._base_type  # pylint: disable-msg=protected-access
      json_type = data_type.json_type
    json_format = data_type.values.get('format')

    if json_type == 'string' and (json_format == 'int64'
                                  or json_format == 'uint64'):
      element.SetTemplateValue('requiresJsonString', True)


class JavaLanguageModel(LanguageModel):
  """A LanguageModel tuned for Java."""

  _JSON_STRING_IMPORT = 'com.google.api.client.json.JsonString'
  _JSON_STRING_TEMPLATE_VALUE = 'requiresJsonString'

  # Dictionary of json type and format to its corresponding data type and
  # import definition. The first import in the imports list is the primary
  # import.
  TYPE_FORMAT_TO_DATATYPE_AND_IMPORTS = {
      ('boolean', None): ('Boolean', ImportDefinition(['java.lang.Boolean'])),
      ('any', None): ('Object', ImportDefinition(['java.lang.Object'])),
      ('integer', 'int16'): ('Short', ImportDefinition(['java.lang.Short'])),
      ('integer', 'int32'): ('Integer',
                             ImportDefinition(['java.lang.Integer'])),
      # We prefer Long here over UnsignedInteger because Long has built-in
      # support for autoboxing in Java.
      ('integer', 'uint32'): ('Long', ImportDefinition(['java.lang.Long'])),
      ('number', 'double'): ('Double', ImportDefinition(['java.lang.Double'])),
      ('number', 'float'): ('Float', ImportDefinition(['java.lang.Float'])),
      ('object', None): ('Object', ImportDefinition(['java.lang.Object'])),
      ('string', None): ('String', ImportDefinition(['java.lang.String'])),
      ('string', 'byte'): ('String', ImportDefinition(['java.lang.String'])),
      ('string', 'date'): ('DateTime', ImportDefinition(
          ['com.google.api.client.util.DateTime'])),
      ('string', 'date-time'): ('DateTime', ImportDefinition(
          ['com.google.api.client.util.DateTime'])),
      ('string', 'int64'): ('Long', ImportDefinition(
          ['java.lang.Long', _JSON_STRING_IMPORT],
          [_JSON_STRING_TEMPLATE_VALUE])),
      ('string', 'uint64'): ('UnsignedLong', ImportDefinition(
          ['com.google.common.primitives.UnsignedLong', _JSON_STRING_IMPORT],
          [_JSON_STRING_TEMPLATE_VALUE])),
      }

  _JAVA_KEYWORDS = [
      'abstract', 'assert', 'boolean', 'break', 'byte', 'case', 'catch', 'char',
      'class', 'const', 'continue', 'default', 'do', 'double', 'else', 'enum',
      'extends', 'final', 'finally', 'float', 'for', 'goto', 'if', 'implements',
      'import', 'instanceof', 'int', 'interface', 'long', 'native', 'new',
      'package', 'private', 'protected', 'public', 'return', 'short', 'static',
      'strictfp', 'super', 'switch', 'synchronized', 'this', 'throw', 'throws',
      'transient', 'try', 'void', 'volatile', 'while'
      ]

  # TODO(user): Remove this. We should instead be using fully qualified names
  # for models to avoid collisions. This will be fixed in Bug 6448720.
  _SPECIAL_CLASS_NAMES = [
      # Required because GenericData extends AbstractMap<String, Object>
      'entry'
      ]

  # We can not create classes which match a Java keyword or built in object
  # type.
  RESERVED_CLASS_NAMES = _JAVA_KEYWORDS + _SPECIAL_CLASS_NAMES + [
      'float', 'integer', 'object', 'string', 'true', 'false',
      ]

  def __init__(self):
    super(JavaLanguageModel, self).__init__(class_name_delimiter='.')
    self._type_map = JavaLanguageModel.TYPE_FORMAT_TO_DATATYPE_AND_IMPORTS

    self._SUPPORTED_TYPES['boolean'] = self._Boolean
    self._SUPPORTED_TYPES['integer'] = self._Int

  def _Boolean(self, data_value):
    """Convert provided boolean to language specific literal."""
    return unicode(bool(data_value.value)).lower()

  def _Int(self, data_value):
    """Convert provided int to language specific literal."""
    # Available types can be found in class variables
    code_types = {
        'Short': '%s',
        'Integer': '%s',
        'Long': '%sL',
        }
    try:
      return code_types[data_value.code_type] % long(data_value.value)
    except KeyError:
      raise ValueError(
          ('Provided DataValue (%s) does not present an appropriate Java '
           'annotated code type (%s).') %
          (data_value.value, data_value.code_type))

  @property
  def type_map(self):
    return self._type_map

  def GetCodeTypeFromDictionary(self, def_dict):
    """Convert a json schema type to a suitable Java type name.

    Overrides the default.

    Args:
      def_dict: (dict) A dictionary describing Json schema for this Property.
    Returns:
      A name suitable for use as a class in the generator's target language.
    """
    json_type = def_dict.get('type', 'string')
    json_format = def_dict.get('format')

    datatype_and_imports = self._type_map.get((json_type, json_format))
    if datatype_and_imports:
      # If there is an entry in the type format to datatype and imports
      # dictionary set it as the native format.
      native_format = datatype_and_imports[0]
    else:
      # Could not find it in the dictionary, set it to the json type.
      native_format = utilities.CamelCase(json_type)
    return native_format

  def CodeTypeForArrayOf(self, type_name):
    """Take a type name and return the syntax for an array of them.

    Overrides the default.

    Args:
      type_name: (str) A type name.
    Returns:
      A language specific string meaning "an array of type_name".
    """
    return 'java.util.List<%s>' % type_name

  def CodeTypeForMapOf(self, type_name):
    """Take a type name and return the syntax for a map of String to them.

    Overrides the default.

    Args:
      type_name: (str) A type name.
    Returns:
      A language specific string meaning "an array of type_name".
    """
    return 'java.util.Map<String, %s>' % type_name

  def ToMemberName(self, s, the_api):
    """CamelCase a wire format name into a suitable Java variable name."""
    camel_s = utilities.CamelCase(s)
    if s.lower() in JavaLanguageModel.RESERVED_CLASS_NAMES:
      # Prepend the service name
      return '%s%s' % (the_api.values['name'], camel_s)
    return camel_s[0].lower() + camel_s[1:]

  # pylint: disable-msg=W0613
  def ToSafeClassName(self, s, the_api, parent=None):
    """Convert a name to a suitable class name in Java.

    Subclasses should override as appropriate.

    Args:
      s: (str) A canonical name for data element. (Usually the API wire format)
      the_api: (Api) The API this element is part of. For use as a hint when the
        name cannot be used directly.
      parent: (schema) The parent we use to get a safe class name.
    Returns:
      A name suitable for use as an element in Java.
    """
    safe_class_name = utilities.CamelCase(s)
    if parent:
      for ancestor in parent.full_path:
        if ancestor.safeClassName == safe_class_name:
          safe_class_name = '%s%s' % (parent.class_name, safe_class_name)
    if safe_class_name.lower() in JavaLanguageModel.RESERVED_CLASS_NAMES:
      # Prepend the service name
      safe_class_name = '%s%s' % (utilities.CamelCase(the_api.values['name']),
                                  utilities.CamelCase(s))
    return safe_class_name

  def ToPropertyGetterMethodWithDelim(self, prop_name):
    """Convert a property name to the name of the getter method that returns it.

    Args:
      prop_name: (str) The name of a property.
    Returns:
      A Java specific name of the getter method that returns the specified
      property. Eg: returns .getXyz for a property called xyz.
    """
    return '%sget%s()' % (self._class_name_delimiter,
                          utilities.CamelCase(prop_name))

  def CodeTypeForVoid(self):
    """Return the Java type name for a void.

    Overrides the default.

    Returns:
      (str) 'EmptyResponse'
    """
    return 'Void'

  def DefaultContainerPathForOwner(self, unused_owner_name, owner_domain):
    """Returns the default path for the module containing this API."""
    # TODO(user): Figure out if this rule is correct. Get decision at PM level
    if owner_domain == 'google.com':
      return 'com/google/api/services'
    return '/'.join(utilities.ReversedDomainComponents(owner_domain))


class Java8LanguageModel(JavaLanguageModel):
  """Language model for the Java 1.8 template version."""

  def CodeTypeForVoid(self):
    """Return the Java 1.8 type name for a void.

    Overrides the default.

    Returns:
      (str) 'EmptyResponse'
    """
    return 'void'


class Java14LanguageModel(JavaLanguageModel):
  """A LanguageModel tuned for Java (version 1.14 and higher)."""

  # TODO(user): lift up this implementation into JavaLanguageModel

  # Dictionary of json type and format to its corresponding data type.
  TYPE_FORMAT_TO_DATATYPE = {
      ('boolean', None): 'java.lang.Boolean',
      ('any', None): 'java.lang.Object',
      ('integer', 'int16'): 'java.lang.Short',
      ('integer', 'int32'): 'java.lang.Integer',
      ('integer', 'uint32'): 'java.lang.Long',
      ('number', 'double'): 'java.lang.Double',
      ('number', 'float'): 'java.lang.Float',
      ('object', None): 'java.lang.Object',
      ('string', None): 'java.lang.String',
      ('string', 'byte'): 'java.lang.String',
      ('string', 'date'): 'com.google.api.client.util.DateTime',
      ('string', 'date-time'): 'com.google.api.client.util.DateTime',
      ('string', 'int64'): 'java.lang.Long',
      ('string', 'uint64'): 'java.math.BigInteger',
      }

  def _Int(self, data_value):
    """Convert provided int to language specific literal."""
    # Available types can be found in class variables
    code_types = {
        'java.lang.Short': '%s',
        'java.lang.Integer': '%s',
        'java.lang.Long': '%sL',
        }
    try:
      return code_types[data_value.code_type] % long(data_value.value)
    except KeyError:
      raise ValueError(
          ('Provided DataValue (%s) does not present an appropriate Java '
           'annotated code type (%s).') %
          (data_value.value, data_value.code_type))

  def GetCodeTypeFromDictionary(self, def_dict):
    """Convert a json schema type to a suitable Java type name.

    Overrides the default.

    Args:
      def_dict: (dict) A dictionary describing Json schema for this Property.
    Returns:
      A name suitable for use as a class in the generator's target language.
    """
    json_type = def_dict.get('type', 'string')
    json_format = def_dict.get('format')

    datatype = (self.TYPE_FORMAT_TO_DATATYPE.get((json_type, json_format)))
    if datatype:
      # If there is an entry in the type format to datatype
      # dictionary set it as the native format.
      native_format = datatype
    else:
      # Could not find it in the dictionary, set it to the json type.
      native_format = utilities.CamelCase(json_type)
    return native_format


class JavaApi(api.Api):
  """An Api with Java annotations."""

  def __init__(self, discovery_doc, **unused_kwargs):
    super(JavaApi, self).__init__(discovery_doc)
    # Java puts the model classes in a module nested under the API, so adjust
    # the path accordingly.
    self.model_module.SetPath('model')

  def TopLevelModelClasses(self):
    """Return the models which are not children of another model.

    Adds an additional constraint on Api.TopLevelModelClasses to remove top
    level schemas which are arrays.

    Returns:
      list of Model.
    """
    return [m for m in self.ModelClasses()
            if not m.parent and not isinstance(m, data_types.ArrayDataType)]

  # pylint: disable-msg=W0613
  def ToClassName(self, s, element, element_type=None):
    """Convert a discovery name to a suitable Java class name.

    In Java, nested class names cannot share the same name as the outer class
    name.

    Overrides the default.

    Args:
      s: (str) A rosy name of data element.
      element: (object) The object we need a class name for.
      element_type: (str) The kind of object we need a class name for.
    Returns:
      A name suitable for use as a class in the generator's target language.
    """
    # Camelcase what we have and account for spaces in canonical names
    name = utilities.CamelCase(s).replace(' ', '')
    if name.lower() in JavaLanguageModel.RESERVED_CLASS_NAMES:
      # Prepend the service name
      service = self._class_name or utilities.CamelCase(self.values['name'])
      return service + name

    if name == self.values.get('className'):
      if 'resource' == element_type:
        name += 'Operations'
      elif 'method' == element_type:
        name += 'Operation'
    return name