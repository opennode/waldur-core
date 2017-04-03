var service_settings_module = (function(self, jQuery){
    var $ = jQuery;

    self.initialize = initialize;

    function initialize(service_fields)   {
        self.service_fields = service_fields;
        $(onDocumentReady);
    }

    function onDocumentReady() {
        $(".services>div").hide();
        $(".services>a").click(function(){
            $(this).next("div").show().load("services/");
        });
        $("#service-settings-content").hide();
        $("#service-settings-toggle").click(function() {
          $("#service-settings-content").slideToggle("slow");
        });

        $("ul#id_type input").each(function() {
            $(this).parent().before(this);
        });

        $(".field-type").change(function(){
            var selectedServiceType = $(".field-type input:checked").val();
            displayOnlyServiceFields(selectedServiceType);
        });
    }

    function displayOnlyServiceFields(serviceName) {
        var formFieldset = $("fieldset.module > div");

        formFieldset.show();
        $.each(formFieldset, function(index, field) {
            var fieldName = getFieldName(field);

            // field can be hidden if there is no errors on the field and it does not belong to the selected service.
            if (!fieldHasAnyError(fieldName) && !fieldBelongsToService(fieldName, serviceName)) {
                $(field).hide();
            }
        });
    }

    function getFieldName(fieldElement) {
        // field element format: "form-row field-name"
        var fieldName = /field-(\w+)$/.exec(fieldElement.className)[1];

        if (fieldName === null) {
            console.log('A service settings stylesheet has been changed. Please updated RegExp.')
        }

        return fieldName;
    }

    function fieldHasAnyError(fieldName) {
        var fieldSelector = "fieldset.module > div.field-" + fieldName;
        return $(fieldSelector + " > ul.errorlist").length !== 0
    }

    function fieldBelongsToService(fieldName, serviceName) {
        var serviceFields = self.service_fields[serviceName];
        return serviceFields.indexOf(fieldName) !== -1;
    }

    return self;
}(service_settings_module || {}, django.jQuery));
