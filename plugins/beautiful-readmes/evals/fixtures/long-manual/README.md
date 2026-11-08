# Ledger

Read and validate local ledger exports. This README is the operator reference.

> Compatibility: format 2 requires Ledger 3.4 or later. Keep a format-1 backup;
> conversion cannot reconstruct comments removed from the original export.

[Inspect](#inspect) · [Validate](#validate) · [Convert](#convert) ·
[Recover](#recover) · [Formats](#formats) · [Exit codes](#exit-codes)

## Inspect

Read the header before choosing a conversion. Inspection does not write files.
A format-1 export can be retained indefinitely when conversion is unnecessary.

## Validate

Validation reports malformed records separately from unsupported format versions.
An unsupported version is not proof that its contents are corrupt.

## Convert

Convert a copy and retain the original. Conversion discards comments; an output
file cannot restore them. Stop when validation fails rather than replacing input.

## Recover

Restore the format-1 backup when comments are needed. Do not label a converted
format-2 export a complete recovery of the original file.

## Formats

Format 1 contains comments and data records. Format 2 contains data records only.
The format number describes the file, while the Ledger version describes a reader.

## Exit codes

Zero means validation completed without errors. A nonzero result needs the stated
diagnostic; it is not permission to delete either the original or the output.

## License

See [LICENSE](LICENSE). The maintained [operator index](docs/index.md) links here.
