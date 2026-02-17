# Licensed to the Software Freedom Conservancy (SFC) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The SFC licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.

from collections.abc import Generator
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any, Optional


def serialize_obj(obj: Any) -> Any:
    """Recursively serialize dataclass objects and complex types to JSON-serializable dicts.
    
    Args:
        obj: The object to serialize.
        
    Returns:
        A JSON-serializable version of the object.
    """
    if obj is None:
        return None
    
    # Handle Path objects
    if isinstance(obj, Path):
        return str(obj)
    
    # Handle dataclass instances
    if is_dataclass(obj) and not isinstance(obj, type):
        return {k: serialize_obj(v) for k, v in asdict(obj).items()}
    
    # Handle dictionaries recursively
    if isinstance(obj, dict):
        return {k: serialize_obj(v) for k, v in obj.items()}
    
    # Handle lists recursively
    if isinstance(obj, (list, tuple)):
        return [serialize_obj(i) for i in obj]
    
    # Return primitive types as-is
    return obj


def command_builder(method: str, params: Optional[dict] = None) -> Generator[dict, dict, dict]:
    """Build a command iterator to send to the BiDi protocol.

    Args:
        method: The method to execute.
        params: The parameters to pass to the method. Default is None.

    Returns:
        The response from the command execution.
    """
    if params is None:
        params = {}
    
    # Serialize any dataclass objects in params
    params = serialize_obj(params)

    command = {"method": method, "params": params}
    cmd = yield command
    return cmd
