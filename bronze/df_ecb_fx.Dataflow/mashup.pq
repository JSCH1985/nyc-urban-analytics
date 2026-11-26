section Section1;

shared ecb_usd_eur = let
    Source = Csv.Document(
        Web.Contents(
            "https://data-api.ecb.europa.eu",
            [RelativePath = "service/data/EXR/D.USD.EUR.SP00.A", Query = [format = "csvdata", startPeriod = "2018-12-01"]]
        ),
        [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]
    ),
    Headers = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),
    Selected = Table.SelectColumns(Headers, {"TIME_PERIOD", "OBS_VALUE", "OBS_STATUS"}),
    Renamed = Table.RenameColumns(Selected, {{"TIME_PERIOD", "rate_date"}, {"OBS_VALUE", "usd_per_eur"}, {"OBS_STATUS", "obs_status"}}),
    Typed = Table.TransformColumnTypes(Renamed, {{"rate_date", type date}, {"usd_per_eur", type number}, {"obs_status", type text}}, "en-US"),
    Loaded = Table.AddColumn(Typed, "loaded_at", each DateTimeZone.RemoveZone(DateTimeZone.UtcNow()), type datetime)
in
    Loaded;
