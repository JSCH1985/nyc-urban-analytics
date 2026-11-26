section Section1;

shared OpenAQGet = (path as text, query as record) as record =>
    Function.InvokeAfter(
        () => Json.Document(
            Web.Contents(
                "https://api.openaq.org",
                [
                    RelativePath = path,
                    Query = query,
                    Headers = [#"X-API-Key" = "{{OPENAQ_API_KEY}}", Accept = "application/json"]
                ]
            )
        ),
        #duration(0, 0, 0, 1.1)
    );

shared OpenAQPaged = (path as text, query as record) as list =>
    let
        Fetch = (page as number) as list => OpenAQGet(path, query & [limit = "1000", page = Text.From(page)])[results],
        Pages = List.Generate(
            () => [Page = 1, Results = Fetch(1)],
            each [Results] <> null,
            each [Page = [Page] + 1, Results = if List.Count([Results]) < 1000 then null else Fetch([Page] + 1)],
            each [Results]
        )
    in
        List.Combine(Pages);

shared OpenAQSensors = () as list =>
    List.Combine(
        List.Transform(
            OpenAQPaged("v3/locations", [bbox = "-74.2591,40.4774,-73.7004,40.9176", monitor = "true"]),
            (location) => List.Transform(
                List.Select(location[sensors], (sensor) => List.Contains({"pm25", "no2", "o3"}, sensor[parameter][name])),
                (sensor) => [
                    location_id = location[id],
                    location_name = location[name],
                    provider = Record.FieldOrDefault(Record.FieldOrDefault(location, "provider", null) ?? [], "name", null),
                    timezone = Record.FieldOrDefault(location, "timezone", null),
                    latitude = location[coordinates][latitude],
                    longitude = location[coordinates][longitude],
                    sensor_id = sensor[id],
                    parameter = sensor[parameter][name],
                    units = sensor[parameter][units]
                ]
            )
        )
    );

shared openaq_sensors = let
    Columns = {"location_id", "location_name", "provider", "timezone", "latitude", "longitude", "sensor_id", "parameter", "units"},
    Source = Table.FromRecords(OpenAQSensors(), Columns, MissingField.UseNull),
    Typed = Table.TransformColumnTypes(
        Source,
        {
            {"location_id", Int64.Type}, {"location_name", type text}, {"provider", type text}, {"timezone", type text},
            {"latitude", type number}, {"longitude", type number}, {"sensor_id", Int64.Type}, {"parameter", type text}, {"units", type text}
        }
    ),
    Loaded = Table.AddColumn(Typed, "loaded_at", each DateTimeZone.RemoveZone(DateTimeZone.UtcNow()), type datetime)
in
    Loaded;

shared openaq_hours_landing = let
    To = DateTimeZone.UtcNow(),
    From = To - #duration(3, 0, 0, 0),
    Stamp = (value as datetimezone) as text => DateTimeZone.ToText(DateTimeZone.ToUtc(value), [Format = "yyyy-MM-dd'T'HH:mm:ss'Z'", Culture = "en-US"]),
    Rows = List.Combine(
        List.Transform(
            OpenAQSensors(),
            (sensor) => List.Transform(
                OpenAQPaged("v3/sensors/" & Text.From(sensor[sensor_id]) & "/hours", [datetime_from = Stamp(From), datetime_to = Stamp(To)]),
                (hour) => [
                    sensor_id = sensor[sensor_id],
                    parameter = sensor[parameter],
                    units = sensor[units],
                    period_start_utc = DateTimeZone.RemoveZone(DateTimeZone.ToUtc(DateTimeZone.From(hour[period][datetimeFrom][utc]))),
                    period_start_local = hour[period][datetimeFrom][local],
                    value = hour[value],
                    observed_count = Record.FieldOrDefault(Record.FieldOrDefault(hour, "coverage", null) ?? [], "observedCount", null),
                    percent_coverage = Record.FieldOrDefault(Record.FieldOrDefault(hour, "coverage", null) ?? [], "percentCoverage", null)
                ]
            )
        )
    ),
    Columns = {"sensor_id", "parameter", "units", "period_start_utc", "period_start_local", "value", "observed_count", "percent_coverage"},
    Source = Table.FromRecords(Rows, Columns, MissingField.UseNull),
    Typed = Table.TransformColumnTypes(
        Source,
        {
            {"sensor_id", Int64.Type}, {"parameter", type text}, {"units", type text}, {"period_start_utc", type datetime},
            {"period_start_local", type text}, {"value", type number}, {"observed_count", Int64.Type}, {"percent_coverage", type number}
        }
    ),
    Loaded = Table.AddColumn(Typed, "loaded_at", each DateTimeZone.RemoveZone(DateTimeZone.UtcNow()), type datetime)
in
    Loaded;
