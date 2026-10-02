"""
app/plugins/sources/kafka_source.py
------------------------------------
Source plugin for consuming data records from Kafka topics.

plugin_type: "kafka"

Uses :class:`~app.messaging.kafka_consumer.KafkaConsumerClient` to pull a batch of
JSON records from a Kafka topic and converts them into a pandas DataFrame.
"""

from __future__ import annotations

import pandas as pd

from app.messaging.kafka_consumer import KafkaConsumerClient
from app.plugins.base import PluginConfigError, SourcePlugin
from app.plugins.registry import registry


@registry.register_source
class KafkaSource(SourcePlugin):
    """
    Reads data from a Kafka topic and returns it as a DataFrame.

    Required config keys
    --------------------
    topic : str
        Name of the Kafka topic to consume from.
    group_id : str
        Consumer group ID for tracking partition offsets.

    Optional config keys
    --------------------
    max_messages : int, default 1000
        Maximum number of records to consume in a single batch.
    timeout : float, default 10.0
        Wall-clock timeout in seconds to wait for messages.
    """

    plugin_type = "kafka"

    def read(self, config: dict) -> pd.DataFrame:
        """
        Consume a batch of records from Kafka and convert to a DataFrame.

        Parameters
        ----------
        config : dict
            Must contain ``"topic"`` and ``"group_id"``.

        Returns
        -------
        pandas.DataFrame
            Records consumed from Kafka as DataFrame rows.

        Raises
        ------
        PluginConfigError
            If required config keys are missing or consumption fails.
        """
        self._require(config, "topic", "group_id")
        topic: str = config["topic"]
        group_id: str = config["group_id"]
        max_messages: int = config.get("max_messages", 1000)
        timeout: float = float(config.get("timeout", 10.0))

        try:
            consumer = KafkaConsumerClient(topic=topic, group_id=group_id)
            try:
                records = consumer.consume_batch(
                    max_messages=max_messages, timeout=timeout
                )
            finally:
                consumer.close()
        except Exception as exc:
            raise PluginConfigError(
                f"KafkaSource: failed to consume from topic '{topic}' (group '{group_id}'): {exc}"
            ) from exc

        if not records:
            return pd.DataFrame()

        return pd.DataFrame(records)
