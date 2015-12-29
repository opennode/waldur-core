from django.forms.widgets import Widget, TextInput
from django.forms.utils import flatatt
from django.utils.html import format_html
from django.utils.encoding import force_text
from django.utils.safestring import mark_safe
from taggit.utils import edit_string_for_tags

from nodeconductor.openstack import Types


class LicenseWidget(Widget):

    def render(self, name, value, attrs=None):
        self.tag_name = name
        self.tag_value = value

        rows = '<br>'.join([
            self.render_license('OS', Types.PriceItems.LICENSE_OS, Types.Os.CHOICES),
            self.render_license('Application', Types.PriceItems.LICENSE_APPLICATION, Types.Applications.CHOICES),
            self.render_license('Support', Types.PriceItems.SUPPORT, Types.Support.CHOICES),
            '<br>Extra tags: %s' % TextInput().render(
                name, edit_string_for_tags([t.tag for t in self.tag_value]), attrs=None)
        ])

        return mark_safe('<p>%s</p>' % rows)

    def render_license(self, title, name, choices):
        field_name = '%s_%s' % (self.tag_name, title.lower())
        final_attrs = self.build_attrs(None, type='hidden', name=field_name, value=name)
        html = format_html('{}: <input{} />', title, flatatt(final_attrs))

        tags = []
        val1 = val2 = ''
        for tag in self.tag_value:
            if tag.tag.name.startswith(name):
                opts = tag.tag.name.split(':')[1:]
                if len(opts) > 1:
                    val1, val2 = opts
                else:
                    val1 = opts[0]
                    val2 = dict(choices).get(val1)
            else:
                tags.append(tag)

        self.tag_value = tags

        final_attrs = self.build_attrs(None, name=field_name)
        output = [format_html('<select{}>', flatatt(final_attrs))]
        output.append('<option value="">None</option>')
        for opt, txt in choices:
            selected = ' selected="selected"' if opt == val1 else ''
            output.append(format_html(
                '<option value="{}"{}>{}</option>', opt, selected, force_text(txt)))
        output.append('</select>')

        html += '\n'.join(output)

        final_attrs = self.build_attrs(None, type='text', name=field_name, value=val2, placeholder='Custom name')
        html += format_html('<input{} />', flatatt(final_attrs))

        return html
