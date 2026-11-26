section Section1;

shared worldbank_gdp = let
    Response = Json.Document(
        Web.Contents(
            "https://api.worldbank.org",
            [
                RelativePath = "v2/country/USA/indicator/NY.GDP.MKTP.CD",
                Query = [format = "json", per_page = "100", date = "2019:" & Text.From(Date.Year(DateTime.LocalNow()))]
            ]
        )
    ),
    Rows = Table.FromRecords(
        List.Transform(
            Response{1},
            each [
                country_code = Record.Field(_, "countryiso3code"),
                year = Record.Field(_, "date"),
                gdp_usd = Record.Field(_, "value"),
                obs_status = Record.Field(_, "obs_status")
            ]
        )
    ),
    Typed = Table.TransformColumnTypes(Rows, {{"country_code", type text}, {"year", Int64.Type}, {"gdp_usd", type number}, {"obs_status", type text}}, "en-US"),
    WithValues = Table.SelectRows(Typed, each [gdp_usd] <> null),
    Loaded = Table.AddColumn(WithValues, "loaded_at", each DateTimeZone.RemoveZone(DateTimeZone.UtcNow()), type datetime)
in
    Loaded;
