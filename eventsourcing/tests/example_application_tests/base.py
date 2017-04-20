from time import sleep

from eventsourcing.application.policies import CombinedPersistencePolicy
from eventsourcing.domain.model.snapshot import Snapshot
from eventsourcing.example.application import ExampleApplication
from eventsourcing.example.domainmodel import Example
from eventsourcing.example.infrastructure import ExampleRepository
from eventsourcing.infrastructure.activerecord import AbstractActiveRecordStrategy
from eventsourcing.infrastructure.eventstore import AbstractEventStore, EventStore
from eventsourcing.tests.sequenced_item_tests.base import WithActiveRecordStrategies


class WithExampleApplication(WithActiveRecordStrategies):
    def construct_application(self):
        cipher = self.construct_cipher()
        app = ExampleApplication(
            integer_sequenced_active_record_strategy=self.integer_sequence_active_record_strategy,
            timestamp_sequenced_active_record_strategy=self.timestamp_sequence_active_record_strategy,
            snapshot_active_record_strategy=self.snapshot_active_record_strategy,
            always_encrypt=bool(cipher),
            cipher=cipher,
        )
        return app

    def construct_cipher(self):
        return None


class ExampleApplicationTestCase(WithExampleApplication):
    def test(self):
        """
        Checks the example application works in the way an example application should.
        """

        with self.construct_application() as app:
            # Check there's a stored event repo.
            self.assertIsInstance(app.integer_sequenced_active_record_strategy, AbstractActiveRecordStrategy)

            # Check there's an event store for version entity events.
            self.assertIsInstance(app.integer_sequenced_event_store, EventStore)
            self.assertEqual(app.integer_sequenced_event_store.active_record_strategy,
                             app.integer_sequenced_active_record_strategy)

            # Check there's an event store for timestamp entity events.
            self.assertIsInstance(app.timestamp_sequenced_event_store, EventStore)
            self.assertEqual(app.timestamp_sequenced_event_store.active_record_strategy,
                             app.timestamp_sequenced_active_record_strategy)

            # Check there's a persistence policy.
            self.assertIsInstance(app.persistence_policy, CombinedPersistencePolicy)

            # Check there's an example repository.
            self.assertIsInstance(app.example_repository, ExampleRepository)

            # Register a new example.
            example1 = app.create_new_example(a=10, b=20)
            self.assertIsInstance(example1, Example)

            # Check the example is available in the repo.
            entity1 = app.example_repository[example1.id]
            self.assertEqual(10, entity1.a)
            self.assertEqual(20, entity1.b)
            self.assertEqual(example1, entity1)

            # Change attribute values.
            entity1.a = 50

            # Check the attribute has the new value.
            self.assertEqual(50, entity1.a)

            # Check the new value is available in the repo.
            entity1 = app.example_repository[example1.id]
            self.assertEqual(50, entity1.a)

            # Take a snapshot of the entity.
            snapshot1 = app.example_repository.event_player.take_snapshot(entity1.id)
            self.assertEqual(snapshot1.entity_id, entity1.id)
            self.assertEqual(snapshot1.entity_version, entity1.version - 1)

            # Take another snapshot of the entity (should be the same event).
            sleep(0.0001)
            snapshot2 = app.example_repository.event_player.take_snapshot(entity1.id)
            self.assertEqual(snapshot1, snapshot2)

            # Check the snapshot exists.
            snapshot2 = app.example_repository.event_player.snapshot_strategy.get_snapshot(entity1.id)
            self.assertIsInstance(snapshot2, Snapshot)
            self.assertEqual(snapshot1, snapshot2)

            # Change attribute values.
            entity1.a = 100

            # Check the attribute has the new value.
            self.assertEqual(100, entity1.a)

            # Check the new value is available in the repo.
            entity1 = app.example_repository[example1.id]
            self.assertEqual(100, entity1.a)

            # Check the old value is available in the repo.
            entity1_v1 = app.example_repository.get_entity(entity1.id, lte=0)
            self.assertEqual(entity1_v1.a, 10)
            entity1_v2 = app.example_repository.get_entity(entity1.id, lte=1)
            self.assertEqual(entity1_v2.a, 50)
            entity1_v3 = app.example_repository.get_entity(entity1.id, lte=2)
            self.assertEqual(entity1_v3.a, 100)

            # Take another snapshot of the entity.
            snapshot4 = app.example_repository.event_player.take_snapshot(entity1.id)

            # Check the new snapshot is not equal to the first.
            self.assertNotEqual(snapshot1, snapshot4)

            # Check the new value still available in the repo.
            self.assertEqual(100, app.example_repository[example1.id].a)

            # Remove all the stored items and check the new value is still available (must be in snapshot).
            self.assertEqual(len(list(app.integer_sequenced_active_record_strategy.all_records())), 3)
            for record in app.integer_sequenced_active_record_strategy.all_records():
                self.integer_sequence_active_record_strategy.delete_record(record)
            self.assertFalse(list(app.integer_sequenced_active_record_strategy.all_records()))
            self.assertEqual(100, app.example_repository[example1.id].a)

            # Check only some of the old values are available in the repo.
            entity1_v1 = app.example_repository.get_entity(entity1.id, lte=0)
            self.assertEqual(entity1_v1, None)
            entity1_v3 = app.example_repository.get_entity(entity1.id, lte=1)
            self.assertEqual(entity1_v3.a, 50)
            entity1_v3 = app.example_repository.get_entity(entity1.id, lte=2)
            self.assertEqual(entity1_v3.a, 100)
