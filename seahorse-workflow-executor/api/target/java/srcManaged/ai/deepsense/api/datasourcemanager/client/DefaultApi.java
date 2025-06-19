package ai.deepsense.api.datasourcemanager.client;

import ai.deepsense.api.datasourcemanager.CollectionFormats.*;


import retrofit2.Call;
import retrofit2.http.*;

import okhttp3.RequestBody;

import ai.deepsense.api.datasourcemanager.model.Error;
import ai.deepsense.api.datasourcemanager.model.Datasource;
import ai.deepsense.api.datasourcemanager.model.DatasourceParams;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

public interface DefaultApi {
  /**
   * 
   * 
   * @param xSeahorseUserid Seahorse user id. When used in frontend this parameter is set by proxy. (required)
   * @param datasourceId  (required)
   * @return Call&lt;Void&gt;
   */
  
  @DELETE("datasources/{datasourceId}")
  Call<Void> deleteDatasource(
    @Header("x-seahorse-userid") String xSeahorseUserid, @Path("datasourceId") String datasourceId
  );

  /**
   * 
   * 
   * @param xSeahorseUserid Seahorse user id. When used in frontend this parameter is set by proxy. (required)
   * @param datasourceId  (required)
   * @return Call&lt;Datasource&gt;
   */
  
  @GET("datasources/{datasourceId}")
  Call<Datasource> getDatasource(
    @Header("x-seahorse-userid") String xSeahorseUserid, @Path("datasourceId") String datasourceId
  );

  /**
   * 
   * Returns list of all datasources
   * @param xSeahorseUserid Seahorse user id. When used in frontend this parameter is set by proxy. (required)
   * @return Call&lt;List<Datasource>&gt;
   */
  
  @GET("datasources")
  Call<List<Datasource>> getDatasources(
    @Header("x-seahorse-userid") String xSeahorseUserid
  );

  /**
   * 
   * Creates a new datasource or overrides datasource for given id
   * @param xSeahorseUserid Seahorse user id. When used in frontend this parameter is set by proxy. (required)
   * @param xSeahorseUsername Seahorse user name. When used in frontend this parameter is set by proxy. (required)
   * @param datasourceId  (required)
   * @param datasourceParams  (required)
   * @return Call&lt;Datasource&gt;
   */
  
  @PUT("datasources/{datasourceId}")
  Call<Datasource> putDatasource(
    @Header("x-seahorse-userid") String xSeahorseUserid, @Header("x-seahorse-username") String xSeahorseUsername, @Path("datasourceId") String datasourceId, @Body DatasourceParams datasourceParams
  );

}
