#!/usr/bin/env python
#
# Copyright 2012 Google Inc. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Support for composite queries without indexes."""



import pickle

from __mimic import common
from __mimic.util import patch

from google.appengine.api import datastore
from google.appengine.datastore import datastore_index
from google.appengine.datastore import datastore_pb
from google.appengine.datastore import datastore_query


class _FakeBatch(object):
  """A fake datastore_query.Batch that returns canned results.

  This class intentionally does not inherit from datastore_query.Batch because
  the default implementation is more likely to hurt than to help.

  Attributes:
    results: The list of results (entities or keys).
  """

  def __init__(self, results):
    self.results = results


class _FakeBatcher(datastore_query.Batcher):
  """A fake datastore_query.Batcher that consists of a single _FakeBatch."""

  def __init__(self, results):
    self._batch = _FakeBatch(results)

  def next_batch(self, unused_min_batch_size):  # pylint: disable-msg=C6409
    """Return the next batch, or None if no more batches remain."""
    batch = self._batch
    self._batch = None  # future calls will return None
    return batch


def _WidenQueryProto(query_pb):
  """Return a simple query that is a superset of the requested query.

  Args:
    query_pb: A datastore_pb.Query object that requires a composite index.

  Returns:
    A datastore_pb.Query object that does not require a composit index, or
    None if the original query cannot be widened.
  """

  # Check for features that cannot be handled.
  if (query_pb.has_compiled_cursor() or
      query_pb.has_end_compiled_cursor()):
    return None

  # Assume that most fields carry over intact.
  wide_pb = datastore_pb.Query()
  wide_pb.CopyFrom(query_pb)

  # Remove any offset/limit since we'll apply those later.
  wide_pb.clear_offset()
  wide_pb.clear_limit()

  # Only keep EQUAL filters.
  eq_filters = [f for f in query_pb.filter_list() if f.op == f.EQUAL]
  wide_pb.clear_filter()
  for f in eq_filters:
    wide_pb.add_filter().CopyFrom(f)

  # Remove orders.
  #
  # TODO: technically we could support a single ascending
  # order, but since we're going to buffer everything in memory it
  # doesn't matter if we leave any orders in the widened query.  If in
  # the future we stream results for queries that are only widened due
  # to filters then it might be beneficial to leave the orders intact
  # if they consist of a single ascending order.
  wide_pb.clear_order()

  # The keys-only field must be set to False since the full entities are
  # requires for post-processing.
  wide_pb.set_keys_only(False)

  return wide_pb


@patch.NeedsOriginal
def _CustomQueryRun(original, query, conn, query_options=None):
  query_pb = query._to_pb(conn, query_options)  # pylint: disable-msg=W0212
  # Check if composite index is required.
  req, kind, ancestor, props = datastore_index.CompositeIndexForQuery(query_pb)
  if req:
    # Keep track of the composite index for generation of index.yaml text.
    props = datastore_index.GetRecommendedIndexProperties(props)
    index_yaml = datastore_index.IndexYamlForQuery(kind, ancestor, props)
    _RecordIndex(index_yaml)

    wide_pb = _WidenQueryProto(query_pb)
    if wide_pb is not None:
      # pylint: disable-msg=W0212
      wide_query = datastore_query.Query._from_pb(wide_pb)
      # TODO: query_options are ignored here since we pass None.
      # It might be possible to pass query_options through - future
      # investigation is required.
      batcher = original(wide_query, conn, None)
      results = []
      for batch in batcher:
        results.extend([entity.ToPb() for entity in batch.results])
      # Apply the original query and slice.
      results = datastore_query.apply_query(query, results)
      offset = query_options.offset or 0
      limit = query_options.limit
      if limit is None:
        limit = len(results)
      results = results[offset:offset+limit]
      # Convert protos to to entities or keys.
      if query_pb.keys_only():
        results = [datastore.Entity.FromPb(pb).key() for pb in results]
      else:
        results = [datastore.Entity.FromPb(pb) for pb in results]
      return _FakeBatcher(results)

  # The query is either a simple query or a composite query that cannot be
  # widened - invoke the normal Query.run() implementation and let it fulfill
  # the request or raise an exception.
  return original(query, conn, query_options=query_options)


def CompositeQueryPatch():
  """Return a Patch that enables composite queries without indexes."""
  return patch.AttributePatch(datastore_query.Query, 'run', _CustomQueryRun)


def _WriteIndexes(indexes):
  """Persist the set of index entries.

  Args:
    indexes: A set of strings, each of which defines a composite index.
  """
  encoded = pickle.dumps(indexes, pickle.HIGHEST_PROTOCOL)
  common.SetPersistent(common.PERSIST_INDEX_NAME, encoded)


def _ReadIndexes():
  """Retrieve the set of index entries.

  Returns:
    A set of strings, each of which defines a composite index.
  """
  encoded = common.GetPersistent(common.PERSIST_INDEX_NAME)
  if encoded is not None:
    try:
      return pickle.loads(encoded)
    except Exception:  # pylint: disable-msg=W0703
      pass
  return set()


def _RecordIndex(index):
  """Add the index spec (a string) to the set of indexes used."""
  indexes = _ReadIndexes()
  indexes.add(index)
  _WriteIndexes(indexes)


def ClearIndexYaml():
  """Reset the index.yaml data to contain no indexes."""
  _WriteIndexes(set())


def GetIndexYaml():
  """Retrieve the specifications for all composite indexes used so far.

  Returns:
    A string suitable for use in an index.yaml file.
  """
  indexes = _ReadIndexes()
  return 'indexes:\n\n' + '\n\n'.join(sorted(indexes))
