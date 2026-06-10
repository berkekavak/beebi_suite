"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Banner, Button, Card, Field, Select, Spinner } from "@/components/ui";

export default function TablePicker({ onLoaded }) {
  const [catalogs, setCatalogs] = useState([]);
  const [schemas, setSchemas] = useState([]);
  const [tables, setTables] = useState([]);
  const [catalog, setCatalog] = useState("");
  const [schema, setSchema] = useState("");
  const [table, setTable] = useState("");
  const [limit, setLimit] = useState(100000);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api
      .catalogs()
      .then((r) => {
        setCatalogs(r.catalogs);
        const def = r.catalogs.includes("workspace") ? "workspace" : r.catalogs[0];
        setCatalog(def || "");
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  // catalog -> schemas. `active` guards against a slower response from a
  // previous catalog overwriting the current one.
  useEffect(() => {
    if (!catalog) return;
    let active = true;
    api
      .schemas(catalog)
      .then((r) => {
        if (!active) return;
        setSchemas(r.schemas);
        setSchema(r.schemas.includes("default") ? "default" : r.schemas[0] || "");
      })
      .catch((e) => active && setError(e.message));
    return () => {
      active = false;
    };
  }, [catalog]);

  // (catalog, schema) -> tables. Skips until a schema for THIS catalog is set,
  // which prevents the cross-catalog "schema does not exist" race.
  useEffect(() => {
    if (!catalog || !schema) return;
    let active = true;
    api
      .tables(catalog, schema)
      .then((r) => {
        if (!active) return;
        setTables(r.tables);
        setTable(r.tables[0] || "");
      })
      .catch((e) => active && setError(e.message));
    return () => {
      active = false;
    };
  }, [catalog, schema]);

  // Changing a level synchronously clears everything below it, so an effect
  // never fires with a stale (catalog, schema) pair.
  function changeCatalog(c) {
    setError("");
    setSchemas([]);
    setSchema("");
    setTables([]);
    setTable("");
    setCatalog(c);
  }

  function changeSchema(s) {
    setError("");
    setTables([]);
    setTable("");
    setSchema(s);
  }

  async function load() {
    setBusy(true);
    setError("");
    try {
      const data = await api.load({ catalog, schema, table, limit: Number(limit) });
      onLoaded({ selection: { catalog, schema, table, limit: Number(limit) }, data });
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  if (loading) {
    return (
      <Card className="p-6">
        <Spinner label="Connecting to Databricks…" />
      </Card>
    );
  }

  return (
    <Card className="p-6">
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Field label="Catalog">
          <Select value={catalog} onChange={changeCatalog} options={catalogs} />
        </Field>
        <Field label="Schema">
          <Select value={schema} onChange={changeSchema} options={schemas} />
        </Field>
        <Field label="Table">
          <Select value={table} onChange={setTable} options={tables} />
        </Field>
        <Field label="Row limit" hint="0 = all rows. Sample large tables.">
          <input
            type="number"
            min={0}
            step={10000}
            value={limit}
            onChange={(e) => setLimit(e.target.value)}
            className="w-full rounded-lg border border-line bg-white px-3 py-2 text-sm outline-none focus:border-honey focus:ring-2 focus:ring-honey-100"
          />
        </Field>
      </div>

      {error && (
        <div className="mt-4">
          <Banner tone="error">{error}</Banner>
        </div>
      )}

      <div className="mt-5 flex items-center gap-3">
        <Button onClick={load} disabled={!table || busy}>
          {busy ? "Loading…" : "Load table"}
        </Button>
        {busy && <Spinner label="Reading from the SQL Warehouse…" />}
      </div>
    </Card>
  );
}
