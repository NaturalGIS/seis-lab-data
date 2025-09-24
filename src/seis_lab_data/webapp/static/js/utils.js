const slugify = (text) => {
    return text
    .toString()
    .normalize('NFKD')  // Unicode Normalization Form of a given string.
    .replace( /[\u0300-\u036f]/g, '' )
    .toLowerCase()
    .trim()
    .replace(/\s+/g, '-')         // Replace spaces with -
    .replace(/[^\w\-]+/g, '')     // Remove all non-word chars
    .replace(/\_/g,'-')           // Replace _ with -
    .replace(/\-\-+/g, '-')       // Replace multiple - with single -
    .replace(/\-$/g, '');         // Remove trailing -
}

export { slugify }
